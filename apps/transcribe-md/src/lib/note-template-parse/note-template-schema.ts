// ============================================================================
// Note-format customization — Phase 2a parse schemas (Zod)
// ----------------------------------------------------------------------------
// Structured-output contracts for the two LLM calls in the parse engine:
//   1. ParsedTemplateLlmSchema — the parse extracts a doctor's note FORMAT.
//   2. PhiScanSchema           — the separate PHI-detection gate over output.
//
// SAFETY BY SHAPE: the parse output deliberately has NO `preamble` /
// `globalRules` — the immutable anti-hallucination safety layer is sourced at
// generation time from the canonical system default (Phase 1) and can never
// be produced by the parse. The parsed styleProfile is doctor-level prose
// style only (tense/tone/abbreviations). `defaultTextMode` is NOT in the LLM
// schema — the engine forces `scaffold_confirm` (never `always_include`) in
// code, so a parsed default is always behind doctor confirmation.
// ============================================================================

import { z } from 'zod';
import type {
  NoteTemplateSection,
  SectionFormatHint,
} from '@/worker/note-templates/system-default-template';

/** Persisted-field length caps, shared by the review/save Zod schema
 *  (reviewed-template.ts) and the parse engine's pre-validation clamp so the
 *  two never drift. The LLM output schema stays UNBOUNDED — the engine clamps a
 *  generated draft to these before it leaves the parse (see clampDraftToLimits),
 *  so a verbose generated value can never break review/save. `tense` is 120
 *  (raised from 60: a tense descriptor can be a short phrase, parallel to
 *  `tone`). */
export const TEMPLATE_FIELD_LIMITS = {
  name: 120,
  encounterType: 80,
  key: 80,
  label: 120,
  styleInstructions: 2000,
  defaultText: 8000,
  tense: 120,
  tone: 120,
  abbreviations: 200,
} as const;

export const FormatHintSchema = z.enum(['prose', 'bullets', 'numbered']);

/** A section as the LLM is allowed to emit it — note: NO defaultTextMode
 *  (forced to scaffold_confirm in code) and NO safety fields. */
export const ParsedSectionLlmSchema = z.object({
  /** Canonical slug where it matches (subjective/objective/ros/pe/assessment/
   *  plan/patient_education/…); else a slugified version of the label. */
  key: z.string().min(1),
  /** The doctor's own heading label (preserved verbatim). */
  label: z.string().min(1),
  order: z.number().int().nonnegative(),
  formatHint: FormatHintSchema,
  /** Generic formatting/phrasing guidance for the section. Format/style only,
   *  never patient content. Null when none. */
  styleInstructions: z.string().nullable(),
  /** ONLY clearly-generic reusable/normal templated text (e.g. a normal-exam
   *  boilerplate). Null when nothing is safely generic. Never patient-unique. */
  defaultText: z.string().nullable(),
});

/** Doctor-level prose style. NO preamble/globalRules (safety is immutable +
 *  generation-time, per Phase 1). */
export const ParsedStyleProfileLlmSchema = z.object({
  tense: z.string().nullable(),
  tone: z.string(),
  abbreviations: z.string().nullable(),
});

/** The full structured output of the parse LLM call. */
export const ParsedTemplateLlmSchema = z.object({
  /** A short human label for the template, e.g. "Ortho follow-up". Must NOT
   *  contain patient identifiers. */
  name: z.string().min(1),
  /** Specialty / visit-type slug if evident, else null. */
  encounterType: z.string().nullable(),
  sections: z.array(ParsedSectionLlmSchema).min(1),
  styleProfile: ParsedStyleProfileLlmSchema,
  /** Phrases the model was UNSURE about (possible patient specifics it chose
   *  to OMIT). Surfaced to the doctor in 2b review — never auto-included. */
  flags: z.array(z.string()),
});
export type ParsedTemplateLlmOutput = z.infer<typeof ParsedTemplateLlmSchema>;

/** Output of the PHI-detection gate call. */
export const PhiScanSchema = z.object({
  /** Field paths that contain patient-specific PHI (names, dates, ages, IDs,
   *  specific findings/values/sites). e.g. "sections[2].defaultText",
   *  "name", "sections[0].label". Empty when clean. */
  phiFields: z.array(z.string()),
  /** True if the model is unsure about ANY field (forces a conservative
   *  reject even when phiFields is empty). */
  anyUncertain: z.boolean(),
});
export type PhiScanResult = z.infer<typeof PhiScanSchema>;

/** Doctor-level style on the returned draft. */
export interface ParsedStyleProfile {
  tense: string | null;
  tone: string;
  abbreviations: string | null;
}

/** The DRAFT template the parse returns (2b reviews + persists it; nothing is
 *  persisted in 2a). Sections carry the forced defaultTextMode. */
export interface ParsedTemplateDraft {
  name: string;
  encounterType: string | null;
  sections: NoteTemplateSection[];
  styleProfile: ParsedStyleProfile;
}

/** Result of parseNoteToTemplate — either a clean draft + review flags, or a
 *  rejection (PHI couldn't be safely removed). The source note is never in
 *  here and never persisted. */
export type ParseNoteResult =
  | { rejected: false; template: ParsedTemplateDraft; flags: string[] }
  | { rejected: true; template: null; reason: string };

export type { NoteTemplateSection, SectionFormatHint };

// ── Generated-value clamping ────────────────────────────────────────────────
// The parse LLM schema is intentionally lenient (min only). Before a draft
// leaves the engine we hard-cap each string field to TEMPLATE_FIELD_LIMITS so
// the draft is ALWAYS review/save-schema-valid — a long generated name/label/
// tense can never surface a raw Zod "Too big" or block the parse. Truncation
// only removes content (PHI-neutral); applied BEFORE the PHI gate so the gate
// scans the final values. The doctor edits anything truncated in review.

function clampStr(value: string, max: number): string {
  const t = value.trim();
  return t.length > max ? t.slice(0, max).trimEnd() : value;
}
function clampNullable(value: string | null, max: number): string | null {
  return value == null ? null : clampStr(value, max);
}

/** Clamp every generated string field of a parsed draft to its persisted cap. */
export function clampDraftToLimits(draft: ParsedTemplateDraft): ParsedTemplateDraft {
  const L = TEMPLATE_FIELD_LIMITS;
  return {
    name: clampStr(draft.name, L.name),
    encounterType: clampNullable(draft.encounterType, L.encounterType),
    sections: draft.sections.map((s) => ({
      ...s,
      key: clampStr(s.key, L.key),
      label: clampStr(s.label, L.label),
      styleInstructions: clampNullable(s.styleInstructions, L.styleInstructions),
      defaultText: clampNullable(s.defaultText, L.defaultText),
    })),
    styleProfile: {
      tense: clampNullable(draft.styleProfile.tense, L.tense),
      tone: clampStr(draft.styleProfile.tone, L.tone),
      abbreviations: clampNullable(draft.styleProfile.abbreviations, L.abbreviations),
    },
  };
}
