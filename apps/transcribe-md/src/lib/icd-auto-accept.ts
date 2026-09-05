// ============================================================================
// SIGN-TIME AUTO-ACCEPT — the pure layer.
// ----------------------------------------------------------------------------
// At signature, a suggested code the doctor never touched is written as an
// ACCEPTED decision carrying `auto: true`, so the signed record says what was
// coded rather than leaving the question open forever. Nothing here reaches a
// database; the route owns the write and the transaction.
//
// ⚠️ THE THRESHOLD IS THE ONE PRODUCT DECISION IN THIS FILE, AND IT IS NOT
// DATA-DERIVED — BECAUSE IT CANNOT BE. Production holds ZERO coding decisions
// (0 of 58 visits, 0 of 12,361 audit rows), so there is no corpus of doctor
// behaviour to fit a number to, and a number fitted to an empty set is an
// invention wearing a measurement's clothes. It is taken instead from the
// GENERATOR'S OWN CONTRACT — `07a-icd-coding.ts:337` defines the bands it is
// asked to emit against:
//
//     >=0.9    explicit diagnosis statement
//     0.7-0.9  strongly implied by findings + plan
//     0.5-0.7  reasonable inference, worth doctor review
//     <0.5     speculative
//
// `>=0.9` is the ONLY band whose own description says the note states the
// diagnosis outright. Every band below it describes an INFERENCE, and an
// inference is exactly the thing a doctor is for. Deliberately NOT `>=0.8`,
// which the same file uses for the `high` badge: a badge is advisory and this
// writes a billable code onto a signed record, so they are different questions
// that happen to be asked of the same number.
//
// ⚠️ SURFACED TO THE OWNER AS A PRODUCT CALL. The mechanism is ordered; the
// number is a statement about what the product IS, and this file's job is to
// make changing it a one-line edit with the reasoning attached.
// ============================================================================

import {
  normalizeIcdCode,
  readIcdDecisions,
  suggestedIcdCodes,
  type IcdDecisionMap,
} from './icd-decisions';

export const ICD_AUTO_ACCEPT_MIN_CONFIDENCE = 0.9;

/**
 * Per-code confidence, keyed by NORMALISED code.
 *
 * ⚠️ `z.number().min(0).max(1)` IS THE GENERATOR'S SCHEMA
 * (`07a-icd-coding.ts:39`), so a schema-valid row is always a 0-1 fraction and
 * a raw comparison against the threshold is sound. Anything OUTSIDE that range
 * is not rescaled — it is DROPPED.
 *
 * ⚠️ AND THAT IS THE OPPOSITE OF WHAT THE DISPLAY PATH DOES, ON PURPOSE. The
 * view renders `confidence * (confidence <= 1 ? 100 : 1)` — it GUESSES the
 * scale, because guessing wrong there costs a wrong percentage on screen.
 * Guessing wrong HERE costs an auto-accepted diagnosis: a `90` read as a
 * fraction clears a 0.9 threshold, and so does `2`. A value this file cannot
 * interpret is a value it refuses, and the code then reaches the doctor as
 * HELD — the direction that asks a question rather than answering one.
 */
export function readSuggestedConfidence(rawIcdCodes: unknown): Record<string, number> {
  const out: Record<string, number> = {};
  const rows = Array.isArray(rawIcdCodes)
    ? rawIcdCodes
    : rawIcdCodes && typeof rawIcdCodes === 'object'
      ? ((rawIcdCodes as { codes?: unknown }).codes ?? [])
      : [];
  if (!Array.isArray(rows)) return out;
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue;
    const r = row as Record<string, unknown>;
    const code = normalizeIcdCode(r.code);
    // FIRST WINS, matching `suggestedIcdCodes` — a duplicated code collapses
    // into its first row there, so reading a LATER row's confidence here would
    // score one code against another code's number.
    if (!code || code in out) continue;
    const c = r.confidence;
    if (typeof c !== 'number' || !Number.isFinite(c) || c < 0 || c > 1) continue;
    out[code] = c;
  }
  return out;
}

export interface IcdAutoAcceptResult {
  /** The full map to store — existing records plus whatever was added. */
  decisions: IcdDecisionMap;
  /** The codes this call added, in the suggester's own order. */
  added: string[];
}

/**
 * The decision map as it should stand once the note is signed.
 *
 * ⚠️ IT ADDS AND IT NEVER REPLACES. A code already carrying a record is left
 * exactly as it is — and the case that matters is a REJECTION, because
 * overwriting one would put a code the doctor threw out onto the signed record
 * as accepted, by a machine, with no trace that they had said no. The guard is
 * `code in existing`, which is presence, not state: it cannot be defeated by a
 * state this file has not heard of.
 *
 * ⚠️ ORPHANED AND DROPPED CODES CANNOT BE REACHED FROM HERE, structurally
 * rather than by a check: the loop iterates `suggestedIcdCodes`, and an
 * orphaned code is by definition NOT in it, while a dropped code never entered
 * the suggested set at all.
 */
export function autoAcceptIcdDecisions(
  rawIcdCodes: unknown,
  rawIcdDecisions: unknown,
  actor: { at: string; byUserId: string },
  minConfidence: number = ICD_AUTO_ACCEPT_MIN_CONFIDENCE,
): IcdAutoAcceptResult {
  const existing = readIcdDecisions(rawIcdDecisions);
  const confidence = readSuggestedConfidence(rawIcdCodes);
  const decisions: IcdDecisionMap = { ...existing };
  const added: string[] = [];

  // A malformed actor is a refusal, not a repair. `byUserId` lands in a column
  // client components read and `at` is the forensic timestamp — writing a
  // placeholder for either would produce a record that looks authoritative and
  // names nobody.
  if (
    typeof actor.byUserId !== 'string' ||
    actor.byUserId.length === 0 ||
    typeof actor.at !== 'string' ||
    actor.at.length === 0
  ) {
    return { decisions, added: [] };
  }

  for (const code of suggestedIcdCodes(rawIcdCodes)) {
    if (code in existing) continue;
    const c = confidence[code];
    // An ABSENT confidence is not a high one. `undefined >= 0.9` is false, but
    // it is written as an explicit presence test so the fail-closed reading is
    // in the source rather than in JavaScript's coercion rules.
    if (typeof c !== 'number' || c < minConfidence) continue;
    decisions[code] = { state: 'accepted', at: actor.at, byUserId: actor.byUserId, auto: true };
    added.push(code);
  }

  return { decisions, added };
}
