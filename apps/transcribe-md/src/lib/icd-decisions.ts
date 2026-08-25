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

export interface IcdDecisionRecord {
  state: IcdDecisionState;
  /** ISO-8601. When the doctor made this decision. */
  at: string;
  /** The user id of the actor. A user id, never a name — this column is read
   *  by client components and an id is not PHI. */
  byUserId: string;
}

export type IcdDecisionMap = Record<string, IcdDecisionRecord>;

/** The only refusal the pure layer can produce. Everything else the route
 *  refuses before it gets here (auth, ownership, signed, status, payload). */
export type IcdDecisionRefusal = 'code_not_suggested';

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
    out[code] = { state, at: rec.at, byUserId: rec.byUserId };
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
  intent: { code: string; decision: IcdDecisionIntent; userId: string; at: string },
): ApplyIcdDecisionResult {
  const code = normalizeIcdCode(intent.code);
  const suggested = new Set(suggestedIcdCodes(input.rawIcdCodes));
  if (!code || !suggested.has(code)) return { ok: false, reason: 'code_not_suggested' };

  const decisions = readIcdDecisions(input.rawIcdDecisions);
  const from = decisions[code]?.state ?? null;
  const to = intent.decision === 'cleared' ? null : intent.decision;

  if (from === to) {
    return { ok: true, changed: false, decisions, from, to };
  }

  const next: IcdDecisionMap = { ...decisions };
  if (to === null) delete next[code];
  else next[code] = { state: to, at: intent.at, byUserId: intent.userId };

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
