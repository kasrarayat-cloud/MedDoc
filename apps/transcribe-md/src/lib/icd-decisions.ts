// ============================================================================
// F8-S1 — THE ICD DECISION SUBSTRATE. PURE, CLIENT-SAFE LEAF.
// ----------------------------------------------------------------------------
// F8's build is a DECISION SURFACE over an engine that already emits the right
// shape. This file is the half of it that has no database, no session and no
// React in it: what a decision IS, where it is stored, and what the stored
// state PROJECTS to.
//
// ⚠️ A DECISION IS A SEPARATE FACT FROM THE SUGGESTION, AND IT LIVES IN A
// SEPARATE COLUMN. Two reasons, and the second one is the load-bearing one:
//
//   1. `icdCodes` is the SUGGESTER's output — the model's proposal plus its
//      verbatim evidence. A doctor accepting a code does not edit the model's
//      proposal, and writing the decision into that blob would blur the two
//      records that a coding dispute needs kept apart.
//
//   2. ⚠️ `07a-icd-coding.ts:570-573` REPLACES `icdCodes` WHOLESALE —
//      `data: { icdCodes: filtered }`, not a merge. Anything hung off that
//      blob is whatever the last L7a run says it is. A separate column removes
//      that coupling outright rather than relying on L7a never running again.
//
// So decisions live in `transcribe_visits.icdDecisions`, which no pipeline
// layer writes.
//
// ⚠️ AND THAT CREATES THE BUCKET THIS FILE NAMES `orphaned`: because the two
// columns move independently, `codes[]` can in principle change under a
// decision that already exists. A decision whose code is NO LONGER SUGGESTED
// is neither accepted nor undecided — it is a decision about a code this note
// no longer carries, and it must NOT flow into the record. Named bucket, and
// the partition reconciles against it, per AGENTS.md: "name every bucket the
// scan can sort an item into, and assert the total."
//
// ⚠️ HONEST LIMIT, AND AN EARLIER DRAFT OF THIS HEADER GOT IT WRONG. That
// draft said a re-run "would destroy" the decisions and that a retry rewrites
// `codes[]`. **Measured by reading the shipped writers, the orphan path is
// UNREACHABLE TODAY:**
//
//   · `icdCodes` has exactly ONE writer — `07a-icd-coding.ts:572`
//   · `layer-skip.ts:101` skips L7a whenever `icdCodes` `hasContent`, and
//     `hasContent` is true for ANY non-null JSON — `{}` and `[]` included
//   · `POST /api/visits/[id]/retry` re-enqueues without clearing the column,
//     so a READY visit's codes survive a retry and L7a does not re-run
//   · `actions/soap.ts` and `actions/rescore-em.ts` only READ the column
//
// So this is a PROPERTY of the code, not a fact about today's corpus, and the
// bucket is DEFENSIVE. What RE-ARMS it, with no change to this file: any path
// that clears or rewrites `icdCodes` on a visit that already has content — a
// "re-code this note" action, a force-rerun flag on L7a, a widening of
// `clearAutomationColumn` to a READY visit, or a manual data repair.
// Established by READING those writers, never by exercising a re-run.
//
// ⚠️ ONE MATCHER FOR BOTH PATHS. `normalizeIcdCode` is used to key the stored
// map AND to test membership of the suggested set. A read path and a write path
// that resolve an identifier with two different matchers is a recorded failure
// class in this repo (the chat-editor silent no-op).
//
// Do NOT add imports to this file beyond types — it is imported by client
// components, and the E/M extractor next door carries the same rule for the
// same reason (`em-coding/icd-rows.ts`).
// ============================================================================

import { extractIcdRows } from './em-coding/icd-rows';

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/** The two states a doctor can put a suggested code into. `cleared` is not a
 *  state — it is the ABSENCE of one, so it is spelled as a verb at the call
 *  site and never stored. */
export const ICD_DECISION_STATES = ['accepted', 'rejected'] as const;
export type IcdDecisionState = (typeof ICD_DECISION_STATES)[number];

/** What the caller asks for. `cleared` removes the record (Undo). */
export const ICD_DECISION_INTENTS = ['accepted', 'rejected', 'cleared'] as const;
export type IcdDecisionIntent = (typeof ICD_DECISION_INTENTS)[number];

/**
 * ⚠️ THE REJECTION REASON IS A CLOSED VOCABULARY OF TOKENS. IT IS NEVER FREE
 * TEXT, AND THAT IS RULING #154 (PROVISIONAL), NOT A STYLE CHOICE.
 *
 * F8-S2's acceptance walk requires *"reject one code WITH A REASON"*, so a
 * reason had to exist. The only question was its SHAPE, and this column is
 * read by client components and mirrored into audit metadata — the two places
 * this repository has been most careful to keep free of patient context.
 *
 * ⚠️ A DOCTOR-TYPED REASON IS PHI-CAPABLE, AND NOTHING DOWNSTREAM COULD TELL.
 * `#148(d)` already stores `{code, fromState, toState}` and NOTHING else,
 * reasoning verbatim that `07a-icd-coding.ts:471-473` records that a free-form
 * description "can carry patient context". `#149(d)` forbids storing a
 * model-authored string for the same reason. A free-text box on a rejection is
 * the same hazard wearing the clinician's hand instead of the model's — *"not
 * relevant, patient's mother had this not him"* is a sentence a real doctor
 * would type, and it would land in a JSONB column the browser reads.
 *
 * So the reason is a TOKEN. A token cannot carry a patient detail, it is
 * greppable, it aggregates, and widening the set later is a visible edit.
 *
 * ⚠️ HONEST LIMIT, STATED RATHER THAN DESIGNED AROUND: `other` records that the
 * doctor's reason was none of the four, and the actual reason is then NOT
 * RECONSTRUCTABLE. That is the accepted cost of refusing a free-text field, and
 * it is the safe direction — an unrecoverable *reason* is cheaper than an
 * unrecoverable *disclosure*.
 *
 * ⚠️ AND THE ORDER OF THIS ARRAY IS NOT COSMETIC — it is the order the surface
 * offers, so a change here changes what a doctor reaches for first.
 */
export const ICD_REJECTION_REASONS = [
  /** The evidence quote does not support the code. */
  'not_supported_by_note',
  /** Real for this patient, but not addressed at this encounter. */
  'not_this_encounter',
  /** Right family, wrong code — laterality, severity, episode. */
  'wrong_specificity',
  /** Already covered by another code on this visit. */
  'duplicate_of_another_code',
  /** None of the above. See the honest limit above. */
  'other',
] as const;
export type IcdRejectionReason = (typeof ICD_REJECTION_REASONS)[number];

export function isIcdRejectionReason(raw: unknown): raw is IcdRejectionReason {
  return (
    typeof raw === 'string' && (ICD_REJECTION_REASONS as readonly string[]).includes(raw)
  );
}

export interface IcdDecisionRecord {
  state: IcdDecisionState;
  /** ISO-8601. When the doctor made this decision. */
  at: string;
  /** The user id of the actor. A user id, never a name — this column is read
   *  by client components and an id is not PHI. */
  byUserId: string;
  /**
   * ⚠️ PRESENT ON `rejected` AND ABSENT ON `accepted` — a BICONDITIONAL, and
   * both directions are enforced in `applyIcdDecision` rather than left to the
   * caller. Optional in the TYPE because an accepted record genuinely has no
   * reason; "optional" here means *state-dependent*, never *nice to have*.
   */
  reason?: IcdRejectionReason;
  /**
   * ⚠️ TRUE ONLY ON A RECORD THIS SYSTEM WROTE WITHOUT THE DOCTOR — the
   * sign-time auto-accept. ABSENT on every decision a doctor made, and that
   * asymmetry is the point: `auto` is a claim about PROVENANCE, so the safe
   * default when it is missing or malformed is *a human decided this*, which
   * is the reading that gets a record looked at rather than trusted.
   *
   * ⚠️ THE LITERAL TYPE IS `true`, NOT `boolean`. `auto: false` is a third
   * thing to mean "a doctor decided", and the absence of the key already means
   * that — two spellings of one fact is how a reader ends up asking which is
   * authoritative. There is one spelling.
   */
  auto?: true;
}

/**
 * The runtime key list `readIcdDecisions` rebuilds each record from, and the
 * compile-time proof that it is exactly `keyof IcdDecisionRecord`.
 *
 * ⚠️ F8-S1 FILED THIS AS A RESIDUAL AND COULD NOT FIX IT — its branch was
 * already pushed with runs in flight, and canon closes a branch at that moment.
 * This is the fix. The residual read:
 *
 *   > **FORWARD-COMPAT:** if a later slice ADDS a field to `IcdDecisionRecord`,
 *   > a deployment running the OLD narrower would strip it from every decision
 *   > it rewrites. A new field must land in the narrower in the SAME change,
 *   > and a rollback window is a stripping window.
 *
 * ⚠️ **A COMMENT WOULD NOT HAVE BEEN A FIX.** The narrower rebuilds each record
 * field by field, so a field added to the interface and forgotten here is
 * stripped by every reader, silently, with `tsc` green — and then WRITTEN BACK
 * NARROWED the next time any decision on that visit changes, because
 * `applyIcdDecision` spreads the narrowed map. That is data loss with no error
 * anywhere. The two assertions below convert it into a compile error:
 * `_NoFieldUnwritten` fails when the interface gains a key this list lacks, and
 * `_NoKeyUnknown` fails in the other direction.
 *
 * ⚠️ **THE ROLLBACK HALF OF THE RESIDUAL IS NOT CURED BY THIS AND CANNOT BE.**
 * An old image running against a new column still narrows what it does not know
 * about. What this buys is that the field can never be forgotten going FORWARD;
 * the deploy-order rule stands and is restated at `readIcdDecisions`.
 */
export const ICD_DECISION_RECORD_KEYS = ['state', 'at', 'byUserId', 'reason', 'auto'] as const;

type _NoFieldUnwritten =
  Exclude<keyof IcdDecisionRecord, (typeof ICD_DECISION_RECORD_KEYS)[number]> extends never
    ? true
    : never;
type _NoKeyUnknown =
  Exclude<(typeof ICD_DECISION_RECORD_KEYS)[number], keyof IcdDecisionRecord> extends never
    ? true
    : never;
/* eslint-disable @typescript-eslint/no-unused-vars */
const _decisionFieldsAreWritten: _NoFieldUnwritten = true;
const _decisionKeysAreKnown: _NoKeyUnknown = true;
/* eslint-enable @typescript-eslint/no-unused-vars */

export type IcdDecisionMap = Record<string, IcdDecisionRecord>;

/**
 * The refusals the pure layer can produce. Everything else the route refuses
 * before it gets here (auth, ownership, signed, status, payload).
 *
 * ⚠️ THE TWO REASON REFUSALS ARE A BICONDITIONAL, AND BOTH HALVES ARE REAL.
 * `reason_required` is the obvious one. `reason_not_allowed` exists because a
 * caller that attaches a reason to an ACCEPT would otherwise have it stored,
 * and a reader meeting `{state:'accepted', reason:'not_supported_by_note'}`
 * cannot tell whether it is a stale artefact or a decision that means the
 * opposite of what its state says. A record that contradicts itself is worse
 * than a refused request — the same asymmetry `#149(g)` applies to a code that
 * is both suggested and dropped.
 */
export const ICD_DECISION_REFUSALS = [
  'code_not_suggested',
  'reason_required',
  'reason_not_allowed',
] as const;
export type IcdDecisionRefusal = (typeof ICD_DECISION_REFUSALS)[number];

export type ApplyIcdDecisionResult =
  | {
      ok: true;
      /** false ⇒ the requested state is the state already stored. NOTHING is
       *  written and NO audit row is emitted: a no-op is not an event. Same
       *  reasoning as `PROMO_GRANT_CREDITED`, which deliberately does not
       *  record its own `already_granted` case. */
      changed: boolean;
      decisions: IcdDecisionMap;
      from: IcdDecisionState | null;
      to: IcdDecisionState | null;
    }
  | { ok: false; reason: IcdDecisionRefusal };

// ---------------------------------------------------------------------------
// The single matcher
// ---------------------------------------------------------------------------

/**
 * ICD-10-CM codes are case-insensitive on the letter and carry no internal
 * whitespace. Normalising both sides means a client that echoes back `k21.00`
 * resolves to the same record the server wrote for `K21.00`.
 *
 * ⚠️ Returns `''` for anything that is not a usable string. `''` is never a
 * member of the suggested set (`extractIcdRows` drops empty codes), so a
 * garbage code falls into `code_not_suggested` rather than creating a record
 * under an empty key.
 */
export function normalizeIcdCode(raw: unknown): string {
  if (typeof raw !== 'string') return '';
  return raw.trim().toUpperCase();
}

// ---------------------------------------------------------------------------
// Reading
// ---------------------------------------------------------------------------

/**
 * The DISTINCT codes this visit's suggester proposed, normalised.
 *
 * ⚠️ Reads through `extractIcdRows`, which is the repository's ONE normaliser
 * for that column and already handles both shapes seen across migrations —
 * Layer 7a's `{ codes: [...] }` and the legacy bare array. Re-deriving the
 * shape here would be a second implementation of a predicate that already
 * exists, which is how the two drift.
 */
export function suggestedIcdCodes(rawIcdCodes: unknown): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of extractIcdRows(rawIcdCodes)) {
    const code = normalizeIcdCode(row.code);
    if (!code || seen.has(code)) continue;
    seen.add(code);
    out.push(code);
  }
  return out;
}

/** How many suggested rows collapsed into an earlier one. Reported so the
 *  partition below can reconcile against the RAW row count rather than
 *  silently swallowing a duplicate. */
export function duplicateSuggestionCount(rawIcdCodes: unknown): number {
  return extractIcdRows(rawIcdCodes).length - suggestedIcdCodes(rawIcdCodes).length;
}

/**
 * The stored decision map, defensively narrowed.
 *
 * A malformed entry is DROPPED rather than repaired. This column is only ever
 * written by `applyIcdDecision`, so a malformed entry means something else got
 * at it — and inventing a state for it would be asserting a clinical decision
 * nobody made.
 *
 * ⚠️ **DROPPING IS A DELETION, AND IT IS DEFERRED RATHER THAN IMMEDIATE — SAID
 * HERE BECAUSE THIS IS WHERE THE NEXT READER MEETS IT.** The narrowed map is
 * what `applyIcdDecision` spreads, so the malformed entry is not merely hidden:
 * **the next decision the doctor makes on this visit writes the column back
 * without it.** Intended — see above — but it is a deletion of stored data
 * triggered by an unrelated action, which is not what "defensively narrowed"
 * sounds like.
 *
 * ⚠️ **AND THE NARROWER IS FIELD-BY-FIELD, SO ADDING A FIELD IS A TWO-PLACE
 * EDIT.** `ICD_DECISION_RECORD_KEYS` above makes forgetting the second place a
 * `tsc` error. What it cannot make safe is the DEPLOY ORDER: an old image
 * running against a column a new image has widened will strip the new field on
 * every rewrite, so **a rollback window is a stripping window** and a field
 * addition ships before anything writes it.
 */
export function readIcdDecisions(rawIcdDecisions: unknown): IcdDecisionMap {
  if (!rawIcdDecisions || typeof rawIcdDecisions !== 'object') return {};
  if (Array.isArray(rawIcdDecisions)) return {};
  const out: IcdDecisionMap = {};
  for (const [key, value] of Object.entries(rawIcdDecisions as Record<string, unknown>)) {
    const code = normalizeIcdCode(key);
    if (!code) continue;
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue;
    const rec = value as Record<string, unknown>;
    const state = rec.state;
    if (state !== 'accepted' && state !== 'rejected') continue;
    if (typeof rec.at !== 'string' || rec.at.length === 0) continue;
    if (typeof rec.byUserId !== 'string' || rec.byUserId.length === 0) continue;

    // ── THE REASON, AND THE TWO SIDES ARE DELIBERATELY NOT SYMMETRIC ────────
    //
    // ⚠️ A `rejected` RECORD WITH NO USABLE REASON IS DROPPED, AND THE HARM
    // DIRECTION IS WHY. Dropping returns the code to UNDECIDED, so it surfaces
    // to the doctor again and is decided a second time — over-shooting to the
    // edge, where there is a fence. Keeping it would mean rendering a rejection
    // whose stated rationale is missing or unreadable, and INVENTING one would
    // be asserting a clinical rationale nobody gave. Same policy as every other
    // malformed field above: dropped, never repaired.
    //
    // ⚠️ AN `accepted` RECORD CARRYING A STRAY REASON KEEPS THE RECORD AND
    // DROPS THE FIELD — the opposite resolution, on purpose. The STATE is well
    // formed and it is a real clinical decision a doctor made; deleting it
    // because of an uninterpretable annotation beside it would destroy the
    // decision to punish the annotation. The annotation cannot be honoured
    // (see `reason_not_allowed`), so it is the annotation that goes.
    // ⚠️ `=== true`, NEVER TRUTHY. `auto` is a provenance claim, and the
    // direction of harm is not symmetric: reading a stray `"yes"` or `1` as
    // auto marks a DOCTOR'S decision as machine-made, which is the reading
    // that invites a later sweep to discard it. Anything that is not the
    // literal `true` falls back to the safe default — a human decided this.
    const auto = rec.auto === true ? ({ auto: true } as const) : {};

    if (state === 'rejected') {
      if (!isIcdRejectionReason(rec.reason)) continue;
      // ⚠️ A REJECTION IS NEVER AUTOMATIC TODAY — nothing writes one — but the
      // field is carried rather than dropped here, because a narrower that
      // silently discards a key it can read is the exact defect
      // `ICD_DECISION_RECORD_KEYS` exists to prevent, one field over.
      out[code] = { state, at: rec.at, byUserId: rec.byUserId, reason: rec.reason, ...auto };
    } else {
      out[code] = { state, at: rec.at, byUserId: rec.byUserId, ...auto };
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Writing
// ---------------------------------------------------------------------------

/**
 * Apply one doctor decision to the stored map.
 *
 * ⚠️ THE SUGGESTED SET IS THE AUTHORITY FOR WHAT MAY BE DECIDED. A code the
 * suggester never proposed is refused — there is no evidence quote behind it,
 * and (b)'s allowlist validation happened at generation time, so admitting an
 * arbitrary code here would be a door into the record that bypasses both. The
 * contract's search-add typeahead is a LATER slice and will need its own
 * allowlist check on the way in; it does not come free with this one.
 */
export function applyIcdDecision(
  input: { rawIcdCodes: unknown; rawIcdDecisions: unknown },
  intent: {
    code: string;
    decision: IcdDecisionIntent;
    userId: string;
    at: string;
    /** Required when `decision === 'rejected'`, forbidden otherwise. */
    reason?: unknown;
  },
): ApplyIcdDecisionResult {
  const code = normalizeIcdCode(intent.code);
  const suggested = new Set(suggestedIcdCodes(input.rawIcdCodes));
  if (!code || !suggested.has(code)) return { ok: false, reason: 'code_not_suggested' };

  // ⚠️ THE REASON GATE RUNS BEFORE THE NO-OP CHECK, AND THE ORDER IS
  // LOAD-BEARING. Were it after, re-rejecting an already-rejected code with a
  // GARBAGE reason would take the `from === to` early return and answer
  // `ok: true, changed: false` — a malformed payload reported as a successful
  // no-op. A caller cannot distinguish that from a legitimate re-assertion, so
  // an invalid request would be silently absorbed. Validate the payload, then
  // decide whether it changes anything.
  const hasReason = intent.reason !== undefined && intent.reason !== null;
  if (intent.decision === 'rejected') {
    if (!isIcdRejectionReason(intent.reason)) return { ok: false, reason: 'reason_required' };
  } else if (hasReason) {
    return { ok: false, reason: 'reason_not_allowed' };
  }

  const decisions = readIcdDecisions(input.rawIcdDecisions);
  const existing = decisions[code] ?? null;
  const from = existing?.state ?? null;
  const to = intent.decision === 'cleared' ? null : intent.decision;

  // ⚠️ A NO-OP IS SAMENESS OF THE WHOLE RECORD, NOT JUST OF THE STATE.
  // `rejected(not_supported_by_note) -> rejected(wrong_specificity)` is a
  // DIFFERENT clinical statement about the same code, and a state-only
  // comparison would call it unchanged: nothing written, no audit row, and the
  // doctor's correction discarded while the UI reports success. That is the
  // silent-no-op class this repository has already shipped once.
  const sameState = from === to;
  const sameReason =
    to !== 'rejected' || existing?.reason === (intent.reason as IcdRejectionReason);
  if (sameState && sameReason) {
    return { ok: true, changed: false, decisions, from, to };
  }

  const next: IcdDecisionMap = { ...decisions };
  if (to === null) delete next[code];
  else if (to === 'rejected') {
    next[code] = {
      state: to,
      at: intent.at,
      byUserId: intent.userId,
      reason: intent.reason as IcdRejectionReason,
    };
  } else {
    // No `reason` key at all on an accept — not `reason: undefined`. The two
    // serialise differently through `JSON.stringify` into JSONB, and a stored
    // `"reason": null` would survive the narrower's `isIcdRejectionReason`
    // check as "not a valid reason" on a state that is not supposed to have
    // one — noise in a clinical column with no reader.
    next[code] = { state: to, at: intent.at, byUserId: intent.userId };
  }

  return { ok: true, changed: true, decisions: next, from, to };
}

// ---------------------------------------------------------------------------
// Projecting
// ---------------------------------------------------------------------------

export interface IcdDecisionProjection {
  /** Distinct suggested codes, in the suggester's own order. */
  suggested: string[];
  accepted: string[];
  rejected: string[];
  /** Suggested, and the doctor has not decided. */
  undecided: string[];
  /**
   * ⚠️ A STORED DECISION WHOSE CODE IS NO LONGER SUGGESTED.
   *
   * An orphaned ACCEPT must never flow into the note — the note it was made
   * against is not the note on screen — and an orphaned decision must never be
   * silently discarded either, because the doctor made it. It is surfaced, and
   * it is nobody's default.
   *
   * ⚠️ UNREACHABLE TODAY, DELIBERATELY KEPT. `icdCodes` has one writer and
   * L7a is skipped whenever it has content, so nothing in the shipped code
   * currently orphans a decision. The re-arming conditions are enumerated in
   * this file's header. This bucket is the fail-safe direction of a wrong
   * answer, and it costs nothing while the path stays shut.
   */
  orphaned: string[];
  /** Raw suggested rows that collapsed into an earlier one by code. */
  duplicateSuggestions: number;
  /**
   * The narrowed decision map itself, so a surface can render WHY a code was
   * rejected without a second read of the raw column.
   *
   * ⚠️ EXPOSED SO THERE IS ONE NARROWER, NOT TWO. The alternative — the surface
   * calling `readIcdDecisions` itself — is a read path and a write path
   * resolving the same data with two matchers, which this file's own header
   * names as a shipped defect in this repository. The projection is already the
   * one thing every consumer reads; the reason travels with it.
   */
  decisions: IcdDecisionMap;
}

/**
 * The partition. `accepted + rejected + undecided === suggested.length`, and
 * `orphaned` is disjoint from all three by construction (its members are not
 * in `suggested`). Asserted in the gate rather than trusted here.
 */
export function projectIcdDecisions(
  rawIcdCodes: unknown,
  rawIcdDecisions: unknown,
): IcdDecisionProjection {
  const suggested = suggestedIcdCodes(rawIcdCodes);
  const suggestedSet = new Set(suggested);
  const decisions = readIcdDecisions(rawIcdDecisions);

  const accepted: string[] = [];
  const rejected: string[] = [];
  const undecided: string[] = [];
  for (const code of suggested) {
    const state = decisions[code]?.state;
    if (state === 'accepted') accepted.push(code);
    else if (state === 'rejected') rejected.push(code);
    else undecided.push(code);
  }

  const orphaned = Object.keys(decisions)
    .filter((code) => !suggestedSet.has(code))
    .sort();

  return {
    suggested,
    accepted,
    rejected,
    undecided,
    orphaned,
    duplicateSuggestions: duplicateSuggestionCount(rawIcdCodes),
    decisions,
  };
}

/**
 * The header chip the contract specifies — *"N suggested · N accepted · N needs
 * review"*. Derived from the projection so the chip and the sections can never
 * disagree about the same visit.
 *
 * "needs review" is UNDECIDED plus ORPHANED: both are codes with an open
 * question in front of the doctor, and collapsing orphaned into `accepted` or
 * dropping it would be the refusal-vs-absence collapse AGENTS.md names.
 */
export function icdDecisionSummary(p: IcdDecisionProjection): {
  suggested: number;
  accepted: number;
  needsReview: number;
} {
  return {
    suggested: p.suggested.length,
    accepted: p.accepted.length,
    needsReview: p.undecided.length + p.orphaned.length,
  };
}
