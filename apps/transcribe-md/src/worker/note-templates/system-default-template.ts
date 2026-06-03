// ============================================================================
// System-default note template — the current L4 SOAP format, expressed as data
// ----------------------------------------------------------------------------
// THE additive-guarantee anchor for the note-format customization feature.
// This module is the SINGLE SOURCE OF TRUTH for the seeded system-default
// NoteTemplate row (doctorId = null, isSystemDefault = true). Its content
// mirrors, verbatim, the SOAP format the Layer-4 generator emits today
// (apps/transcribe-md/src/worker/layers/04-generate-soap.ts) — the 4 markdown
// sections in order + every per-section directive + the global guardrails.
//
// WHY THIS EXISTS: in Phase 1, L4 will render the *resolved* template into its
// prompt instead of the hard-coded string array. For a doctor who never
// customizes, resolveActiveTemplate() returns this system default, so the
// rendered prompt must reproduce today's prompt and the note stays byte-
// identical. If this drifts from L4, the additive guarantee breaks — the
// sibling test (__tests__/system-default-template.test.ts) pins it against the
// live `validateSoapStructure` contract + a fixture of L4's directives.
//
// The migration that seeds the row (packages/db/prisma/migrations/<ts>_
// add_note_templates_phase0/migration.sql) inlines the JSON serialized from
// THIS constant; a drift test reads that SQL back and deep-equals it here so
// the DB seed and this module can never silently diverge.
//
// NO PHI ever appears here — format/style scaffolding only.
// ============================================================================

/** Stable primary key for the singleton system-default row. Not a cuid (the
 *  column is plain TEXT); a human-readable id keeps the seed idempotent and
 *  the row trivially greppable in prod. */
export const SYSTEM_DEFAULT_TEMPLATE_ID = 'tmpl_system_default_soap';

/** How a section's body should be shaped. Coarse hint; the authoritative
 *  detail lives in `styleInstructions`. */
export type SectionFormatHint = 'prose' | 'bullets' | 'numbered';

/** What to do with a section when the transcript doesn't support it.
 *  `omit_unless_supported` is the only safe mode for the system default —
 *  never scaffold/fabricate content the encounter didn't produce. */
export type SectionDefaultTextMode =
  | 'omit_unless_supported'
  | 'scaffold_confirm'
  | 'always_include';

/** One ordered section of a note template. Persisted as an element of the
 *  `note_templates.sections` JSONB array. */
export interface NoteTemplateSection {
  /** Canonical section slug (subjective/objective/ros/pe/assessment/plan/
   *  patient_education/…). The system default uses the 4 SOAP sections. */
  key: string;
  /** Heading text — rendered as `## {label}` in the note markdown. Must
   *  match the headings the L4 structure validator checks for. */
  label: string;
  /** 1-based render order. */
  order: number;
  formatHint: SectionFormatHint;
  /** Verbatim per-section directive text from L4. Null = no extra guidance. */
  styleInstructions: string | null;
  /** Pre-filled scaffold text. Null for the system default (no scaffolding). */
  defaultText: string | null;
  defaultTextMode: SectionDefaultTextMode;
}

/** Document-level style + the global generation guardrails. Persisted as the
 *  `note_templates.styleProfile` JSONB column. */
export interface NoteTemplateStyleProfile {
  /** Narrative tense override (e.g. "past"). Null = model default. */
  tense: string | null;
  /** Overall voice. */
  tone: string;
  /** Abbreviation policy. Null = model default. */
  abbreviations: string | null;
  /** The L4 system-prompt preamble (the "who you are + use only evidence"
   *  framing). */
  preamble: string;
  /** The verbatim L4 "Critical rules" + the narrow hallucination rules, in
   *  source order. These are guardrails, not stylistic preferences — they
   *  must survive into Phase 1's rendered prompt unchanged. */
  globalRules: string[];
}

/** Content shape of the seeded system-default template (the DB row adds
 *  id/timestamps). Mirrors the persisted columns. */
export interface SystemDefaultTemplate {
  id: string;
  doctorId: null;
  name: string;
  encounterType: null;
  specialtyBaseline: null;
  sections: NoteTemplateSection[];
  styleProfile: NoteTemplateStyleProfile;
  version: number;
  status: 'active';
  isSystemDefault: true;
}

// ── The 4 SOAP sections, verbatim from 04-generate-soap.ts (the markdown
//    headings + each section's directive block). Order matters. ──
const SUBJECTIVE_INSTRUCTIONS = [
  '**Chief Complaint:** …',
  '**HPI:** narrative paragraph incorporating onset, duration, quality,',
  '  severity, location, timing, context, modifying factors, associated',
  '  symptoms.',
  '**PMH:** bullet list or "[not documented]" if silent.',
  '**Medications:** bullet list with dose/route/frequency where stated.',
  '**Allergies:** bullet list with reactions where stated.',
  '**Family History:** brief list or "[not documented]".',
  '**Social History:** smoking / alcohol / drugs / occupation if mentioned;',
  '  omit unmentioned lines.',
  '**ROS:** by system when documented; else the single line',
  '  "ROS not formally documented in this encounter."',
].join('\n');

const OBJECTIVE_INSTRUCTIONS = [
  'Physical exam findings grouped by system. Include vitals if mentioned.',
  'Include test results mentioned. If no formal exam was discussed, write',
  'exactly: "Formal exam not documented in this encounter."',
].join('\n');

const ASSESSMENT_INSTRUCTIONS = [
  'Primary clinical consideration with supporting reasoning. Differentials',
  'if the doctor discussed them. Severity/staging if applicable. Use [not',
  'documented] rather than inventing.',
].join('\n');

const PLAN_INSTRUCTIONS = [
  'Numbered list: diagnostics ordered, medications changed/started, follow-',
  'up, referrals, patient education. Each item should be actionable.',
].join('\n');

/** The verbatim L4 global guardrails (system-prompt "Critical rules" + the
 *  narrow hallucination rules + the output contract), in source order. */
const GLOBAL_RULES: string[] = [
  'Do NOT invent clinical findings. If a claim lacks transcript evidence, either omit it or explicitly mark it "[not documented]".',
  'When information came exclusively from the patient, prefix with "Per patient, …" so the source is clear on downstream review.',
  'Never add test results, medication doses, or vital-sign numbers that were not stated.',
  'Don\'t add diagnostic qualifiers (acute, chronic, undiagnosed, severe, mild, sudden, gradual) unless the transcript uses them explicitly. "Migraines" stays "migraines" — not "undiagnosed migraines." Onset is "sudden" only if the patient said sudden.',
  'Don\'t infer maternal/paternal side or a specific relative when the transcript only mentions a relative type. "My grandmother" stays "grandmother" — not "maternal grandmother" unless stated.',
  'When a dose, frequency, or strength is ambiguous in the transcript, write what was actually said and append \'[clarify with patient]\' rather than picking the most likely value. Don\'t silently resolve "two tablets... one tablet twice a day" to a single interpretation.',
  'Output ONLY the SOAP note markdown. No preamble, no postscript.',
];

/**
 * The seeded system-default template. Encodes today's L4 SOAP format as data.
 * Frozen so no caller can mutate the shared singleton.
 */
export const SYSTEM_DEFAULT_NOTE_TEMPLATE: SystemDefaultTemplate = {
  id: SYSTEM_DEFAULT_TEMPLATE_ID,
  doctorId: null,
  name: 'System Default — SOAP',
  encounterType: null,
  specialtyBaseline: null,
  version: 1,
  status: 'active',
  isSystemDefault: true,
  sections: [
    {
      key: 'subjective',
      label: 'Subjective',
      order: 1,
      formatHint: 'prose',
      styleInstructions: SUBJECTIVE_INSTRUCTIONS,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
    {
      key: 'objective',
      label: 'Objective',
      order: 2,
      formatHint: 'prose',
      styleInstructions: OBJECTIVE_INSTRUCTIONS,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
    {
      key: 'assessment',
      label: 'Assessment',
      order: 3,
      formatHint: 'prose',
      styleInstructions: ASSESSMENT_INSTRUCTIONS,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
    {
      key: 'plan',
      label: 'Plan',
      order: 4,
      formatHint: 'numbered',
      styleInstructions: PLAN_INSTRUCTIONS,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
  ],
  styleProfile: {
    tense: null,
    tone: 'professional medical',
    abbreviations: null,
    preamble:
      'You are a senior clinician writing a SOAP note from a clinical visit. Use ONLY the entities provided and the transcript as evidence. Write in a professional medical tone.',
    globalRules: GLOBAL_RULES,
  },
};
