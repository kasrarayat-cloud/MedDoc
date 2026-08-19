// ============================================================================
// Deep-audit G9 helper — detect a partial L7 failure that should flip
// needsReview + populate a reviewReason for the doctor.
// ----------------------------------------------------------------------------
// The worker's L7 fan-out (worker.ts) runs five tasks via
// Promise.allSettled and rolls per-task outcomes into a
// `confidenceScores` shape:
//
//   {
//     icd_coding:      { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     cpt_coding:      { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     rx_drafting:     { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     referrals:       { ... },
//     patient_summary: { ... },
//   }
//
// Pre-fix, the worker transitioned to status=READY regardless of which
// tasks failed. The doctor would open the visit and see a SOAP with
// empty codes/Rx columns and no banner indicating partial completion.
// Deep-audit G9 documents the demo-blocking scenario where Anthropic
// credit exhaustion mid-pipeline left V3 in this state.
//
// The fix: when ANY of the THREE load-bearing layers (icd-coding /
// cpt-coding / rx-drafting) fails, flip needsReview + populate
// reviewReason so the visit surfaces in the review queue with a
// specific reason + retry CTA. Status stays READY because the SOAP
// itself is valid; the T-M6 design choice (one layer's failure doesn't
// fail the visit) is preserved.
//
// 7d (referrals) and 7e (patient summary) are NOT load-bearing — they
// augment the visit page but the doctor doesn't need them to sign the
// SOAP. Their failures roll up into confidenceScores only.
//
// 2026-05-13 extension (Step 2 of post-cross-input-mode-audit fix matrix,
// closes Finding 2): the helper now ALSO detects the "model returned
// status:ok with codes:[] / em:none" shape. PR #232's UC2 audio_upload
// scenario surfaced this — L7a completed without throwing but emitted
// an empty codes array. Pre-extension G9 didn't catch this because
// status:ok masks the empty output. The helper now accepts an
// optional `outputs` parameter carrying the L7a + L7b results; when
// the output is empty despite status:ok the helper flags it with a
// distinct EMPTY label so audit-log forensics can separate "the layer
// crashed" from "the model returned nothing."
// ============================================================================

/** Per-layer outcome shape written into `confidenceScores` by the
 *  worker's L7 fan-out roll-up. Mirrors the inline shape in
 *  apps/transcribe-md/src/worker.ts:775-779. */
export type LayerStatus =
  | { status: 'ok'; metadata?: unknown }
  | { status: 'skipped' }
  | { status: 'failed'; reason: string };

export type AutomationConfidenceScores = Record<string, LayerStatus>;

/** Load-bearing tasks — failure of any of these flips needsReview.
 *  Order matters for `reviewReason` readability (icd → cpt → rx). */
export const LOAD_BEARING_L7_TASKS = [
  'icd_coding',
  'cpt_coding',
  'rx_drafting',
] as const;

export type LoadBearingTaskKey = (typeof LOAD_BEARING_L7_TASKS)[number];

/** Output shapes the helper inspects to catch "empty result with
 *  status:ok" cases. Both shapes are optional — call sites that don't
 *  yet pass them keep the historic failed-only detection behavior. */
export interface IcdLikeResult {
  codes?: ReadonlyArray<unknown>;
}
export interface CptLikeResult {
  em?: { code?: string | null } | null;
  procedures?: ReadonlyArray<unknown>;
  /** Written by L7b when it dropped the E/M half because E/M did not apply to
   *  this visit (F12-c, ruling #127). **Read this instead of recomputing the
   *  verdict** — see `isCptWhollyEmpty` for why that distinction is load-bearing
   *  rather than stylistic. */
  emSuppressed?: boolean;
}

export interface LayerOutputs {
  icdCodes?: IcdLikeResult | null;
  cptCodes?: CptLikeResult | null;
  /** True when L7a was SKIPPED this attempt because a prior attempt already
   *  wrote its column (T-M13 resume). On a FRESH ok run, 07a's own
   *  post-validation (07a-icd-coding.ts:293-320) has ALWAYS already written
   *  the better, specialty-aware empty-codes review flag — so pass 2's icd
   *  branch firing there is pure duplication (the doubled "Auto-coding…
   *  Click Retry" banner on terse visits, 2026-07-02 follow-up). On a
   *  RESUMED attempt the reset at worker attempt-start wiped that flag and
   *  07a never re-runs — pass 2 is the SOLE empty-codes guard there. */
  icdResumed?: boolean;
  /** ⚠️ THERE IS DELIBERATELY NO `emApplies` FIELD HERE, AND ITS ABSENCE IS THE
   *  FIX RATHER THAN AN OMISSION.
   *
   *  An earlier draft carried one, so this helper could tell "the model
   *  produced nothing" from "nobody asked for an E/M". It was RECOMPUTED at
   *  read time, and on the resume path — L7b skipped, the note edited, the
   *  shape flipped — it returned a different answer than the run that produced
   *  the blob. The result was an "Auto-coding incomplete … Click Retry" banner
   *  that Retry could never clear: exactly the failure the parameter had been
   *  added to prevent.
   *
   *  The discriminator is now `cptCodes.emSuppressed`, written by the same L7b
   *  run that produced the `em: null` being judged. A stored fact cannot drift
   *  from the record it is attached to. See `isCptWhollyEmpty`. */
}

/** Distinguishes "the layer crashed" from "the layer returned nothing
 *  successfully." Both flip needsReview, but the audit-log metadata
 *  uses the discriminator so admin forensics can grep separately. */
export type IncompleteCause = 'failed' | 'empty';

export interface IncompleteAutomationResult {
  /** True iff at least one load-bearing layer failed OR returned empty. */
  needsReview: boolean;
  /** Doctor-facing one-line reason; null when nothing tripped. Capped
   *  at 500 chars so a verbose stack trace can't blow past Postgres
   *  TEXT-row sane sizes. */
  reviewReason: string | null;
  /** Which load-bearing layers tripped (subset of LOAD_BEARING_L7_TASKS).
   *  Empty when nothing tripped. */
  failedLayers: LoadBearingTaskKey[];
  /** Per-tripped-layer reason strings, mirror of `reviewReason` but
   *  structured for the audit-log row's metadata field. Each value
   *  truncated to 300 chars. */
  reasonsByLayer: Record<LoadBearingTaskKey, string | null>;
  /** Per-tripped-layer cause discriminator. Helps the audit-log row
   *  separate genuine crashes ('failed') from "model returned nothing
   *  successfully" ('empty'). */
  causeByLayer: Record<LoadBearingTaskKey, IncompleteCause | null>;
}

/** Inspect a confidenceScores roll-up + (optionally) the L7a/L7b
 *  output columns. Reports whether the visit needs review because a
 *  load-bearing L7 task errored OR returned empty.
 *
 *  Backwards-compatible: existing callers that pass only `scores`
 *  keep the historic failed-only detection. Callers that pass
 *  `outputs` get the additional empty-codes detection (closes the
 *  PR #232 Finding 2 / UC2 audio_upload anomaly). */
export function detectIncompleteAutomation(
  scores: AutomationConfidenceScores | null | undefined,
  outputs?: LayerOutputs,
): IncompleteAutomationResult {
  const tripped: LoadBearingTaskKey[] = [];
  const reasonsByLayer: Record<LoadBearingTaskKey, string | null> = {
    icd_coding: null,
    cpt_coding: null,
    rx_drafting: null,
  };
  const causeByLayer: Record<LoadBearingTaskKey, IncompleteCause | null> = {
    icd_coding: null,
    cpt_coding: null,
    rx_drafting: null,
  };

  // Pass 1: scores → 'failed' detection (the original G9 behavior).
  if (scores) {
    for (const key of LOAD_BEARING_L7_TASKS) {
      const entry = scores[key];
      if (entry && entry.status === 'failed') {
        tripped.push(key);
        reasonsByLayer[key] = entry.reason?.slice(0, 300) ?? 'unknown';
        causeByLayer[key] = 'failed';
      }
    }
  }

  // Pass 2: outputs → 'empty' detection. Only inspects layers that
  // weren't ALREADY counted as 'failed' (a failed layer's empty output
  // is a known consequence, not a distinct signal). Only inspects
  // load-bearing layers icd_coding + cpt_coding — rx_drafting is
  // intentionally excluded because many visits legitimately carry no
  // Rx (e.g. derm-biopsy follow-up, screening encounters).
  //
  // F-6 (2026-07-02): pass 2 now also requires the layer's recorded status
  // to be 'ok'. The hard-coded "(status:ok)" text assumed pass 2 could only
  // fire after a successful run — but a layer DISABLED by flags (E/M is
  // suppressed by design for imaging-report specialties; TM_ENABLE_ICD_CPT
  // can disable both coders) records {status:'skipped'} and leaves its
  // column null, which tripped a false "Auto-coding incomplete … Click
  // Retry" banner on EVERY ultrasound visit. Retry could never clear it.
  // SOAP clinic visits always record status:'ok' here, so their check —
  // including the DB-blip defense (re-read failed → outputs null but
  // scores still 'ok') — is byte-identical.
  if (outputs) {
    if (
      outputs.icdResumed === true &&
      scores?.icd_coding?.status === 'ok' &&
      causeByLayer.icd_coding == null &&
      isIcdEmpty(outputs.icdCodes)
    ) {
      tripped.push('icd_coding');
      reasonsByLayer.icd_coding = 'returned empty codes array (status:ok)';
      causeByLayer.icd_coding = 'empty';
    }
    // F12-c — AND THE E/M LEG ONLY ASKS ITS QUESTION WHERE THE ANSWER EXISTS.
    // On an operative note L7b runs, succeeds, emits the procedure codes and
    // returns a null `em` BY DESIGN (ruling #123). "No E&M code emitted" is
    // then a true sentence about a field nobody asked for, and turning it into
    // a doctor-facing "Auto-coding incomplete — click Retry" is the ultrasound
    // banner described above, reappearing through the one door that comment's
    // fix does not cover.
    //
    // ⚠️ THE ALTERNATIVE — trip on an empty PROCEDURES array instead, since an
    // operative note with no procedure code is arguably incomplete — was
    // considered and NOT taken. It ADDS a trip condition that has never
    // existed, on notes whose procedure may legitimately not be codeable, and
    // this change's whole claim is that it removes an E/M and moves nothing
    // else. Narrowing a false positive is reversible; a new banner class is a
    // product decision. Recorded in ruling #127 rather than left implicit here.
    // ⚠️ THE DISCRIMINATOR IS THE STORED MARKER, NEVER A RECOMPUTED VERDICT.
    // `outputs.cptCodes.emSuppressed` was written by the same L7b run that
    // produced the `em: null` being judged here, so the two cannot disagree. An
    // earlier draft asked `emApplies`, recomputed at read time — and on the
    // resume path (L7b skipped, note edited, shape flipped) that recomputation
    // returned TRUE about a blob produced under FALSE, reinstating the exact
    // unclearable banner this whole parameter exists to prevent. Found by two
    // independent refuters; see `07b-cpt-coding.ts`'s `emSuppressed` comment.
    const emWasSuppressed = outputs.cptCodes?.emSuppressed === true;
    if (
      scores?.cpt_coding?.status === 'ok' &&
      causeByLayer.cpt_coding == null &&
      (emWasSuppressed
        ? isCptWhollyEmpty(outputs.cptCodes)
        : isCptEmpty(outputs.cptCodes))
    ) {
      tripped.push('cpt_coding');
      // ⚠️ THE REASON MUST NAME THE RIGHT ABSENCE. "no E&M code emitted" is a
      // FALSE statement about an operative note — nobody asked for one — and a
      // wrong field in a doctor-facing banner is worse than an absent one.
      reasonsByLayer.cpt_coding = emWasSuppressed
        ? 'no codes emitted at all (status:ok)'
        : 'no E&M code emitted (status:ok)';
      causeByLayer.cpt_coding = 'empty';
    }
  }

  if (tripped.length === 0) {
    return {
      needsReview: false,
      reviewReason: null,
      failedLayers: [],
      reasonsByLayer,
      causeByLayer,
    };
  }

  const perLayer = tripped.map((k) => {
    const reason = reasonsByLayer[k] ?? 'unknown';
    return `${k.replace('_', '-')}: ${reason}`;
  });
  const joined = perLayer.join('; ').slice(0, 500);
  return {
    needsReview: true,
    reviewReason: `Auto-coding incomplete — ${joined}. Click Retry to reprocess.`,
    failedLayers: tripped,
    reasonsByLayer,
    causeByLayer,
  };
}

/** Empty when the column is null or codes is missing / not an array /
 *  zero-length. */
function isIcdEmpty(icd: IcdLikeResult | null | undefined): boolean {
  if (icd == null) return true;
  const codes = icd.codes;
  if (!Array.isArray(codes)) return true;
  return codes.length === 0;
}

/** Empty when the column is null or no E&M code was emitted. Procedures
 *  + modifiers being empty does NOT trip the rule — many established-
 *  patient visits legitimately bill only the E&M tier. */
function isCptEmpty(cpt: CptLikeResult | null | undefined): boolean {
  if (cpt == null) return true;
  const em = cpt.em;
  if (em == null) return true;
  const code = em.code;
  return typeof code !== 'string' || code.trim() === '';
}

/** Empty when the layer produced NOTHING — no E/M *and* no procedures.
 *
 *  ⚠️ THIS EXISTS BECAUSE SKIPPING THE E/M LEG WHOLESALE LOST A TRUE POSITIVE,
 *  AND AN ADVERSARIAL PASS CAUGHT IT. The first version of F12-c simply
 *  disabled the empty check when `emApplies` was false. That removed the false
 *  banner it was written for — and also removed the only doctor-facing signal
 *  for a REAL failure on the same notes: the model returning
 *  `{em:null, procedures:[]}`, or every procedure code being rejected by the
 *  allowlist (`07b-cpt-coding.ts` `filteredProcedures` → `[]`). The doctor got a
 *  colonoscopy with an entirely empty Codes tab, no banner and no retry CTA,
 *  and the only trace was a fire-and-forget audit row nobody sees.
 *
 *  So the question asked of an operative note is not *"where is the E/M"* — it
 *  is the SAME question this helper always asked, *"did the layer return
 *  anything successfully"*, phrased for a visit where an E/M was never
 *  expected. It adds no trip condition that did not exist: pre-F12-c this exact
 *  input tripped too, via the `em == null` arm.
 *
 *  ⚠️ IT ALSO RESTORES THE DB-BLIP DEFENCE. The comment above the post-fan-out
 *  re-read in `worker.ts` states that a failed re-read lands the visit in review
 *  "via the cpt-null leg only" — with the leg gated off, a fresh operative-note
 *  attempt whose re-read blipped would have gone READY unflagged, and that
 *  sentence would have become false in the same commit that edited the code it
 *  describes. `cpt == null` is the first thing this returns true for. */
function isCptWhollyEmpty(cpt: CptLikeResult | null | undefined): boolean {
  if (cpt == null) return true;
  if (!isCptEmpty(cpt)) return false;
  const procedures = cpt.procedures;
  return !Array.isArray(procedures) || procedures.length === 0;
}
