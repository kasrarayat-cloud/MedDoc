// ============================================================================
// TOKEN SUBSTITUTION (TOKEN-1) — resolve the closed scaffold token set from the
// VISIT RECORD, deterministically, at fill time. NEVER the model.
// ----------------------------------------------------------------------------
// The closed set and the string-shape helpers live in the pure leaf
// `scaffold-text.ts`. The RESOLVERS live here, because {age} needs the calendar
// arithmetic in `visit-metadata.ts` (which value-imports zod, so this module is
// server-side). Each token maps to a pure function of the VisitPatientRecord
// (+ visitDate); an unresolvable token refuses with a NAMED reason and the
// caller declines the whole insert (the field renders blank) rather than emit a
// half-substituted clinical sentence.
//
// ⚠️ SUBSTITUTION IS A PURE STRING OPERATION ON THE INSERTED TEXT — it does NOT
// mint a `visit_record` fact. The name/age appear only as substrings inside the
// existing `clinician_correction` fact value, so ruling #247's
// `assertNoRecordDerivedFacts` stays satisfied on the certification path.
// ============================================================================
import {
  SUBSTITUTABLE_TOKENS,
  substitutableTokenPattern,
  substitutableTokensIn,
  type SubstitutableToken,
} from './scaffold-text';
import { ageAtDateResolved, type AgeRefusal, type VisitPatientRecord } from './visit-metadata';

/** Why a registered token could not be resolved from the record. `{age}` reuses
 *  the shared record-derived refusal vocabulary; `{patient}` adds the one reason
 *  that vocabulary deliberately lacks (visit-metadata.ts: "a missing name is
 *  simply missing"). */
export type ScaffoldTokenRefusal = 'patient_name_absent' | AgeRefusal;

export interface ScaffoldTokenSubstitution {
  token: SubstitutableToken;
  /** The resolved value that replaced the token. Non-PHI-classified the same as
   *  the record fields it comes from; recorded in the manifest for audit. */
  value: string;
}

export type ScaffoldTokenResult =
  | { ok: true; text: string; substitutions: ScaffoldTokenSubstitution[] }
  | { ok: false; token: SubstitutableToken; reason: ScaffoldTokenRefusal };

function resolveToken(
  token: SubstitutableToken,
  patient: VisitPatientRecord | null | undefined,
  visitDate: Date | string | null | undefined,
): { ok: true; value: string } | { ok: false; reason: ScaffoldTokenRefusal } {
  switch (token) {
    case 'patient': {
      const name = patient?.name?.trim();
      if (!name) return { ok: false, reason: 'patient_name_absent' };
      return { ok: true, value: name };
    }
    case 'age': {
      const age = ageAtDateResolved(patient?.dateOfBirth ?? null, visitDate ?? null);
      if (!age.ok) return { ok: false, reason: age.reason };
      return { ok: true, value: String(age.years) };
    }
    default: {
      // Exhaustiveness: a new token in SUBSTITUTABLE_TOKENS with no resolver
      // here fails the build rather than printing its braces.
      const _never: never = token;
      return { ok: false, reason: 'patient_name_absent' as ScaffoldTokenRefusal };
    }
  }
}

/**
 * Substitute every REGISTERED token in `text` from the record. Returns the
 * substituted text plus the per-token record when ALL present tokens resolve;
 * refuses with the FIRST unresolvable token (in registry order) otherwise. Text
 * with no registered token is returned unchanged with an empty substitution list.
 */
export function substituteScaffoldTokens(
  text: string,
  patient: VisitPatientRecord | null | undefined,
  visitDate: Date | string | null | undefined,
): ScaffoldTokenResult {
  const present = substitutableTokensIn(text);
  if (present.length === 0) return { ok: true, text, substitutions: [] };

  const values = new Map<SubstitutableToken, string>();
  for (const token of SUBSTITUTABLE_TOKENS) {
    if (!present.includes(token)) continue;
    const r = resolveToken(token, patient, visitDate);
    if (!r.ok) return { ok: false, token, reason: r.reason };
    values.set(token, r.value);
  }
  const out = text.replace(substitutableTokenPattern(), (_m, t: string) =>
    values.get(t as SubstitutableToken) ?? _m,
  );
  const substitutions: ScaffoldTokenSubstitution[] = SUBSTITUTABLE_TOKENS.filter((t) =>
    values.has(t),
  ).map((token) => ({ token, value: values.get(token)! }));
  return { ok: true, text: out, substitutions };
}
