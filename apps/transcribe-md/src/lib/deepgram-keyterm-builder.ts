// ============================================================================
// Deepgram keyterm builder — per-visit scoping (2026-05-13)
// ----------------------------------------------------------------------------
// Issues #202 + #206 fix-pack: instead of shipping a single global
// ~124-keyterm list on every visit (which diluted attentional weight
// and missed specialty-specific terms like Implanon / Nexplanon),
// the builder composes a per-visit list from four layers:
//
//   1. CORE_KEYTERMS  — universal anatomy / labs / procedures / common
//                        diagnoses + top-25 cross-specialty medications.
//                        Always loaded.
//
//   2. SPECIALTY_KEYTERMS[specialty] — bundle for the visit's normalized
//                        specialty key. Adds ~20-30 terms specific to
//                        the clinical domain.
//
//   3. Safety floor    — ISMP confused-drug-names. Always loaded.
//                        SLOT for PR-2 — currently empty so PR-1 ships
//                        the scoping skeleton; PR-2 wires the list.
//
//   4. Patient context — current medications + active problems pulled
//                        from QuillMD's known patient record (capped at
//                        15 terms). SLOT for a future PR — currently
//                        accepts the input but no callers pass it yet.
//
// Token-budget enforcement: Deepgram caps keyterms at 500 SUBWORD
// tokens TOTAL (~140 terms at typical ~3.5 tokens each). The builder
// drops in priority order if needed:
//   - Patient context first (lowest priority)
//   - Then specialty bundle tail
//   - Then optional core
// Safety floor is NEVER dropped — if it's defined, it always rides.
//
// Returns the composed list AND metadata so the worker can persist
// `transcribe_visits.keytermsApplied` for audit attribution. If a
// future Implanon → insulin regression appears, the audit row says
// exactly which keyterms ran on that visit.
// ============================================================================

import {
  CORE_KEYTERMS,
  SPECIALTY_KEYTERMS,
} from './deepgram-vocabulary';
import {
  normalizeSpecialty,
  type SpecialtyKey,
} from './specialty-keys';

/** Tokens estimated as `ceil(len / 3.5)` per the existing
 *  deepgram-vocabulary.ts convention. Conservative — actual BPE
 *  varies. */
function estimateTokens(term: string): number {
  return Math.ceil(term.length / 3.5);
}

function estimateTotalTokens(terms: readonly string[]): number {
  let total = 0;
  for (const t of terms) total += estimateTokens(t);
  return total;
}

/** Per-layer metadata for the audit row. Allows correlating a
 *  future transcription regression to the exact keyterm composition
 *  that ran on the visit. */
export interface KeytermsAppliedMetadata {
  specialty: SpecialtyKey;
  rawSpecialty: string | null;
  layers: {
    core: number;
    specialty: number;
    safetyFloor: number;
    patientContext: number;
  };
  totalTerms: number;
  estimatedTokens: number;
  /** True if the budget enforcer had to drop terms. Worth knowing —
   *  consistent budget-overruns signal a bundle that's grown too
   *  large. */
  budgetEnforced: boolean;
  /** SHA-prefix of the final term list, for cheap regression
   *  attribution. Distinct visits with different specialty + patient
   *  context should hash differently; identical context should hash
   *  identically. */
  termsHash: string;
}

export interface KeytermsResult {
  keyterms: string[];
  metadata: KeytermsAppliedMetadata;
}

export interface BuildKeytermsArgs {
  /** Free-text specialty from `transcribe_visits.specialty`. The
   *  builder normalizes internally via `normalizeSpecialty`. */
  specialty: string | null | undefined;
  /** Safety floor — ISMP confused-drug-names. Always rides if
   *  provided. Slot for PR-2; pass undefined or an empty array
   *  from callers until that PR lands. */
  safetyFloor?: readonly string[];
  /** Patient-context boost. Cap at 15 entries; the builder enforces
   *  the cap defensively even if the caller passes more. Slot for a
   *  future PR; callers should pass undefined for now. */
  patientContext?: readonly string[];
  /** Deepgram's hard cap is 500 subword tokens; we hold back 50
   *  for safety margin. Override only in tests. */
  tokenBudget?: number;
}

const DEFAULT_TOKEN_BUDGET = 450;
const PATIENT_CONTEXT_CAP = 15;

/** Cheap non-crypto hash for the metadata.termsHash field. Stable
 *  across runs given identical input. */
function cheapHash(input: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < input.length; i++) {
    const c = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (
    (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(13, '0')
  );
}

/** Compose the per-visit keyterm list. Pure function — no I/O.
 *  Caller is responsible for passing the safety floor (PR-2) and
 *  patient-context (future PR). */
export function buildKeytermsForVisit(
  args: BuildKeytermsArgs,
): KeytermsResult {
  const specialty = normalizeSpecialty(args.specialty);
  const specialtyTerms = SPECIALTY_KEYTERMS[specialty] ?? [];
  const safetyFloor = args.safetyFloor ?? [];
  const patientRaw = args.patientContext ?? [];
  const patientCapped = patientRaw.slice(0, PATIENT_CONTEXT_CAP);
  const budget = args.tokenBudget ?? DEFAULT_TOKEN_BUDGET;

  // Compose in priority order: safety floor > core > specialty >
  // patient context. The Set-based dedupe preserves first-occurrence
  // ordering, so anything in safetyFloor wins precedence over the
  // same string in a lower layer.
  const composed: string[] = [];
  const seen = new Set<string>();
  const layerCounts = { core: 0, specialty: 0, safetyFloor: 0, patientContext: 0 };

  const addLayer = (
    terms: readonly string[],
    layer: keyof typeof layerCounts,
  ) => {
    for (const t of terms) {
      const norm = t.trim();
      if (norm.length === 0) continue;
      const key = norm.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      composed.push(norm);
      layerCounts[layer]++;
    }
  };

  addLayer(safetyFloor, 'safetyFloor');
  addLayer(CORE_KEYTERMS, 'core');
  addLayer(specialtyTerms, 'specialty');
  addLayer(patientCapped, 'patientContext');

  // Budget enforcement — drop in reverse priority if over.
  let budgetEnforced = false;
  let tokens = estimateTotalTokens(composed);
  if (tokens > budget) {
    budgetEnforced = true;
    // Drop patient context first, then specialty tail, never safety
    // floor or core. Walk backwards because composed[] is in
    // safety→core→specialty→patient order; the tail is what we
    // sacrifice.
    while (tokens > budget && composed.length > 0) {
      const last = composed[composed.length - 1];
      if (!last) break;
      // Refuse to drop into safety floor or core. The two
      // protected segments are positions 0 to (safetyFloor + core - 1).
      const protectedCount = layerCounts.safetyFloor + layerCounts.core;
      if (composed.length <= protectedCount) break;
      composed.pop();
      tokens -= estimateTokens(last);
      // Update layer count of the trimmed entry. The trimmed entry
      // is from whichever layer currently sits at the tail.
      if (
        composed.length >=
        layerCounts.safetyFloor + layerCounts.core + layerCounts.specialty
      ) {
        layerCounts.patientContext = Math.max(0, layerCounts.patientContext - 1);
      } else {
        layerCounts.specialty = Math.max(0, layerCounts.specialty - 1);
      }
    }
  }

  const termsHash = cheapHash(composed.join('|'));

  return {
    keyterms: composed,
    metadata: {
      specialty,
      rawSpecialty: args.specialty ?? null,
      layers: layerCounts,
      totalTerms: composed.length,
      estimatedTokens: tokens,
      budgetEnforced,
      termsHash,
    },
  };
}
