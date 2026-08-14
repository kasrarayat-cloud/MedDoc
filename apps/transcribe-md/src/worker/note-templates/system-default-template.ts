// ============================================================================
// System-default note template — the current L4 SOAP format, expressed as data
// ----------------------------------------------------------------------------
// THE additive-guarantee anchor for the note-format customization feature.
// This module is the SINGLE SOURCE OF TRUTH for the seeded system-default
// NoteTemplate row (doctorId = null, isSystemDefault = true). Its content is,
// BYTE-FOR-BYTE, the pieces of the SOAP prompt the Layer-4 generator emitted
// before Phase 1 (apps/transcribe-md/src/worker/layers/04-generate-soap.ts).
//
// Phase 1 (this revision): L4 no longer hard-codes its prompt — it builds it
// from the resolved template via build-soap-prompt.ts. For a non-customizing
// doctor, resolveActiveTemplate() returns this system default, and the builder
// reproduces today's prompt BYTE-FOR-BYTE (locked by the golden test at
// worker/layers/__tests__/l4-golden-prompt.test.ts). Hence: zero behavior
// change. The line-wrapping below is therefore SIGNIFICANT — each
// styleInstructions / globalRules entry mirrors L4's exact wrapped strings so
// the builder, joining them with '\n', reproduces the original prompt.
//
// The migration that seeds + re-syncs the row keeps the JSON in lockstep with
// this constant; a drift test deep-equals the two.
//
// NO PHI ever appears here — format/style scaffolding only.
// ============================================================================

/** Stable primary key for the singleton system-default row. */
export const SYSTEM_DEFAULT_TEMPLATE_ID = 'tmpl_system_default_soap';

/** How a section's body should be shaped. Advisory hint; the authoritative
 *  detail lives in `styleInstructions` (the builder uses formatHint only as a
 *  fallback when a section has no styleInstructions). */
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
// ── Structured elements (feat/structured-templates, 2026-07-02) ────────────
// Real client templates use TABLES and OPTION SETS (checkboxes, circle-one,
// severity picks). These are first-class structure — NOT flattened prose —
// so generation can do CONSTRAINED FILL (only the template's own options,
// only dictated cell values) and render/export can reproduce the layout.
// Optional everywhere: the system default and every pre-existing template
// simply omit it (backward compatible; the seeded-row drift test unaffected).
export type SectionStructure =
  | {
      kind: 'table';
      /** Column headers, in order (verbatim from the doctor's template). */
      columns: string[];
      /** Fixed row labels (e.g. a vitals grid: BP/HR/RR/…). Omitted when the
       *  rows vary per patient (e.g. a medication list). */
      rowLabels?: string[];
    }
  | {
      kind: 'options';
      /** The enumerated choices, verbatim (including the doctor's own typos —
       *  generation may ONLY pick from this list, never invent an option). */
      options: string[];
      /** true = "check all that apply"; false = single-select. */
      multi: boolean;
    };

export interface NoteTemplateSection {
  /** Canonical section slug (subjective/objective/ros/pe/assessment/plan/…). */
  key: string;
  /** Heading text — rendered as `## {label}` in the prompt + the note. Must
   *  match the headings the structure validator checks for. */
  label: string;
  /** 1-based render order. */
  order: number;
  formatHint: SectionFormatHint;
  /** Verbatim per-section directive block from L4 (wrapping preserved). Null =
   *  no explicit guidance (builder falls back to formatHint). */
  styleInstructions: string | null;
  /** Pre-filled scaffold text. Null for the system default (no scaffolding). */
  defaultText: string | null;
  defaultTextMode: SectionDefaultTextMode;
  /** First-class table/option-set structure. Absent/null = prose section
   *  (every template before 2026-07-02, incl. the system default). */
  structure?: SectionStructure | null;
  /** WHERE THIS SECTION'S CONTENT COMES FROM.
   *
   *  The anchored verifier checks a drafted line against the DICTATION. That
   *  is only a meaningful question for a section the dictation is the source
   *  of. A protocol paragraph the template mandates, or a section another
   *  pipeline step produces, has no transcript to be entailed by — verifying
   *  it against one demotes correct content for failing a test that never
   *  applied. Absent = 'dictation', so every existing section is unchanged. */
  provenance?: SectionProvenance;
  /** Lines this template MANDATES verbatim in the section.
   *
   *  A standing closing sentence ("Clinical correlation with the above findings
   *  is required.") is correct because the format requires it, not because the
   *  doctor said it — there is no transcript span for it and there never will
   *  be. Declared here, next to the instructions that mandate it, rather than
   *  as a phrase the verifier happens to know. */
  mandatedLines?: string[];
}

/**
 * Which producer a section's content is answerable to.
 *
 *  • `dictation` — the doctor said it. The anchored verifier's question ("is
 *    this in the transcript?") is the right question. DEFAULT.
 *  • `template`  — the template mandates this prose (a scan protocol, a
 *    standing closing line). It is the doctor's own approved boilerplate, and
 *    it is correct precisely BECAUSE it is fixed, not because it was spoken.
 *  • `other_step` — a later pipeline layer writes it (coding, patient
 *    summary). It anchors to that step's inputs; this layer must not judge it,
 *    and must never evacuate it.
 */
export type SectionProvenance = 'dictation' | 'template' | 'other_step';

/**
 * Sections that appear in the COMPOSED document but are written by a later
 * pipeline step, with how this layer should treat each.
 *
 *  • `PATIENT SUMMARY` — layer 07e. A deliberate re-explanation for the
 *    patient; its phrasing IS the deliverable, so only the clinical facts
 *    inside it are checkable (`facts_only`).
 *  • `PROCEDURES / E&M` — the coding step. Nothing in it is dictated.
 *  • `DIAGNOSES`, `MEDICATIONS` — likewise.
 *
 * Keyed by section name because a heading IS a section's identity here. This is
 * a statement about which producer owns which section, not a list of sentences
 * the verifier is told to ignore.
 */
export const PIPELINE_SECTION_POLICY: Record<string, SectionProvenance> = {
  'patient summary': 'other_step',
  'procedures / e&m': 'other_step',
  'procedures': 'other_step',
  'diagnoses': 'other_step',
  'medications': 'other_step',
};

/** Document-level style + the immutable safety guardrails. Persisted as the
 *  `note_templates.styleProfile` JSONB column. The builder treats `preamble` +
 *  `globalRules` as the IMMUTABLE safety layer (a custom template appends
 *  sections, it never overrides these). */
export interface NoteTemplateStyleProfile {
  tense: string | null;
  tone: string;
  abbreviations: string | null;
  /** The L4 system-prompt preamble (the "who you are + use only evidence"
   *  framing). Multi-line, wrapped exactly as L4. */
  preamble: string;
  /** The verbatim L4 "Critical rules" — one element per logical rule, each
   *  pre-wrapped with its `- ` bullet + `  ` continuations exactly as L4. The
   *  builder emits `Critical rules:` then joins these with '\n'. */
  globalRules: string[];
  /** Per-doctor CONTEXT-field defaults for a custom structured template
   *  (feat/template-context-defaults): a { fieldKey → chosen value } map used
   *  to deterministically fill the never-dictated context {{one of}} slots
   *  (clinic / referring physician / machine / location) at generation. Only a
   *  value that is one of the template's own options for that field is applied;
   *  otherwise the field stays "[not documented]". Absent on the system default
   *  and on every SOAP template → no effect. */
  contextDefaults?: Record<string, string> | null;
  /** Labeled header/short fields parsed from the doctor's form — e.g. an
   *  operative note's PATIENT NAME / PATIENT DOB / PATIENT ID # / DATE OF
   *  SURGERY / SURGEON block (feat/template-header-fields, 2026-07-23). Rendered
   *  at the TOP of the STYLED export in `order`, each filled DETERMINISTICALLY
   *  (never AI) from the visit record / dictation or left an honest blank.
   *  LABELS ONLY — never a patient value (values are export-time). Absent on the
   *  system default + every prose template → no header block. */
  headerFields?: NoteTemplateHeaderField[] | null;
  /** "Form-only export" preference: when true the STYLED export renders ONLY the
   *  doctor's form (header fields + note body) and SUPPRESSES the appended
   *  Diagnoses / Procedures / Medications / Referrals / Patient Summary blocks.
   *  Default OFF; no UI yet (feat/template-header-fields groundwork). */
  formOnlyExport?: boolean | null;
}

/** One labeled header/short field of a parsed form template. LABEL ONLY — it
 *  never carries a patient value; the value is filled at export time. */
export interface NoteTemplateHeaderField {
  /** Canonical fill key: 'patient_name' | 'patient_dob' | 'patient_id' |
   *  'date_of_surgery' | 'surgeon' | a slug for an unmapped field. Drives the
   *  deterministic export-time fill. */
  key: string;
  /** The field's label verbatim from the doctor's form (e.g. "PATIENT NAME:").
   *  Rendered as the field label; NEVER a patient value. */
  label: string;
  /** 1-based render order within the header block. */
  order: number;
}

/** Content shape of the seeded system-default template (the DB row adds
 *  timestamps). */
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

// ── The 4 SOAP section directive blocks — BYTE-FOR-BYTE the lines L4 emits
//    after each `## heading`. Wrapping is load-bearing (see header). ──
const SUBJECTIVE_INSTRUCTIONS = [
  '**Chief Complaint:** …',
  '**HPI:** narrative paragraph incorporating onset, duration,',
  '  quality, severity, location, timing, context, modifying factors,',
  '  associated symptoms.',
  '**PMH:** bullet list or "[not documented]" if silent.',
  '**Medications:** bullet list with dose/route/frequency where stated.',
  '**Allergies:** bullet list with reactions where stated.',
  '**Family History:** brief list or "[not documented]".',
  '**Social History:** smoking / alcohol / drugs / occupation if',
  '  mentioned; omit unmentioned lines.',
  '**ROS:** by system when documented; else the single line',
  '  "ROS not formally documented in this encounter."',
].join('\n');

const OBJECTIVE_INSTRUCTIONS = [
  'Physical exam findings grouped by system. Include vitals if',
  'mentioned. Include test results mentioned. If no formal exam was',
  'discussed, write exactly: "Formal exam not documented in this',
  'encounter."',
].join('\n');

const ASSESSMENT_INSTRUCTIONS = [
  'Primary clinical consideration with supporting reasoning.',
  'Differentials if the doctor discussed them. Severity/staging if',
  'applicable. Use [not documented] rather than inventing.',
].join('\n');

const PLAN_INSTRUCTIONS = [
  'Numbered list: diagnostics ordered, medications changed/started,',
  'follow-up, referrals, patient education. Each item should be',
  'actionable.',
].join('\n');

/** The verbatim L4 system-prompt preamble (lines 132-134 of 04-generate-soap). */
const PREAMBLE = [
  'You are a senior clinician writing a SOAP note from a clinical',
  'visit. Use ONLY the entities provided and the transcript as',
  'evidence. Write in a professional medical tone.',
].join('\n');

/** The verbatim L4 "Critical rules" — one element per logical rule, each with
 *  its exact `- `/`  ` wrapping (lines 173-196 of 04-generate-soap). */
const GLOBAL_RULES: string[] = [
  [
    '- Do NOT invent clinical findings. If a claim lacks transcript',
    '  evidence, either omit it or explicitly mark it "[not documented]".',
  ].join('\n'),
  [
    '- When information came exclusively from the patient, prefix with',
    '  "Per patient, …" so the source is clear on downstream review.',
  ].join('\n'),
  [
    '- Never add test results, medication doses, or vital-sign numbers',
    '  that were not stated.',
  ].join('\n'),
  [
    "- Don't add diagnostic qualifiers (acute, chronic, undiagnosed,",
    '  severe, mild, sudden, gradual) unless the transcript uses them',
    '  explicitly. "Migraines" stays "migraines" — not "undiagnosed',
    '  migraines." Onset is "sudden" only if the patient said sudden.',
  ].join('\n'),
  [
    "- Don't infer maternal/paternal side or a specific relative when",
    '  the transcript only mentions a relative type. "My grandmother"',
    '  stays "grandmother" — not "maternal grandmother" unless stated.',
  ].join('\n'),
  [
    '- When a dose, frequency, or strength is ambiguous in the',
    '  transcript, write what was actually said and append',
    "  '[clarify with patient]' rather than picking the most likely",
    '  value. Don\'t silently resolve "two tablets... one tablet twice',
    '  a day" to a single interpretation.',
  ].join('\n'),
  // 2026-06-11 inaudible-span hardening — the three observed failure modes
  // (garbled drug name asserted as fact; patient-reported sensation written
  // as an exam finding; garble normalized into a specific clinical term).
  [
    '- "[unclear in recording]" in the transcript means the audio was not',
    '  intelligible there. Never guess what it might have been. Never',
    '  assert a medication, dose, diagnosis, finding, or proper name whose',
    '  only evidence overlaps such a marker — reproduce the marker in the',
    '  note instead (e.g. \'prescribed [unclear in recording] — clarify\').',
  ].join('\n'),
  [
    '- Never present patient-reported sensations as examination findings.',
    '  "Sore when I press on it" is Subjective, per patient — it is NOT',
    '  "tender to palpation" unless the transcript documents a clinician',
    '  examination. If no exam occurred, the Objective section says so.',
  ].join('\n'),
  [
    '- Never normalize an unfamiliar, garbled, or partial term into a',
    '  specific drug or clinical term. If a word does not clearly match a',
    '  known medication or condition, quote it as heard with',
    "  '[unclear in recording]' appended rather than substituting the",
    '  closest real term.',
  ].join('\n'),
  [
    '- Never specify or elaborate a medication, device, or product beyond',
    '  what was said — even when the elaboration is pharmacologically',
    '  correct. A brand name stays as said: "Implanon" — do NOT append the',
    '  generic or route ("etonogestrel subdermal implant"). A vague device',
    '  reference stays vague: "your injections" is NOT "adrenaline',
    '  auto-injector" unless the transcript names it.',
  ].join('\n'),
  [
    '- Never assert possession, availability, or causal links that were',
    '  not stated. "Takes salbutamol regularly" does NOT become "had her',
    '  inhaler on hand". Two separately-mentioned facts (a hospitalisation;',
    '  an allergy) are NOT linked into one causal statement unless the',
    '  transcript links them.',
  ].join('\n'),
  // ── NEVER EDITORIALIZE ABOUT THE TEMPLATE OR YOUR OWN PROCESS ─────────
  // ⚠️ POSITION IS LOAD-BEARING: THIS MUST NOT BE THE LAST ELEMENT.
  // `ultrasound-report-template.ts` builds its rules as
  // `SOAP_SAFETY.globalRules.slice(0, -1)` — dropping exactly the SOAP output
  // line below. A rule appended AFTER it reaches primary care and NOT imaging.
  //
  // ⚠️ AND THE SCOPE IS META-COMMENTARY, NOT ABSENCE. The first draft of this
  // clause said "do not say information was missing" and capped the vocabulary
  // at "EMPTY or [not documented] — those are the only two ways". An
  // adversarial pass showed that contradicts THREE instructions in the same
  // built prompt:
  //   · globalRules[7]      "If no exam occurred, the Objective section says so"
  //   · the Objective directive  write exactly: "Formal exam not documented…"
  //   · the ROS directive        the single line "ROS not formally documented…"
  // and, on the imaging route, `write exactly: "No prior study available for
  // comparison."` plus `"[laterality not specified]"`. Four mandated sentences
  // the cap forbade, with no precedence rule anywhere to break the tie.
  //
  // Saying a finding was not documented is CLINICAL CONTENT and is required.
  // What is forbidden is commentary about the TEMPLATE, the DICTATION, or the
  // model's own process. Those are different things and the first draft
  // conflated them.
  [
    '- Write the note and nothing else. Never address the reader and never',
    '  describe your own process. Do not comment on the template, on how well',
    '  the dictation matched it, or on why a section came out as it did.',
    '  Recording that a finding was not documented is clinical content and is',
    '  expected — "Formal exam not documented in this encounter" is the note',
    '  doing its job. "This section could not be completed from the dictation',
    '  provided" is commentary, and does not belong in a medical record.',
  ].join('\n'),
  [
    '- A mismatch between this template and the dictation is NOT yours to',
    '  explain. If the transcript does not support a heading, KEEP THE HEADING',
    '  and leave its body empty, or write "[not documented]". Never delete a',
    '  heading and never write a sentence about the mismatch — the application',
    '  detects it and tells the clinician. An aside about it inside the note is',
    '  an editorial remark in a medical record, and it will be signed.',
  ].join('\n'),
  '- Output ONLY the SOAP note markdown. No preamble, no postscript.',
];

/**
 * The seeded system-default template. Encodes today's L4 SOAP format as data,
 * byte-for-byte. Frozen so no caller can mutate the shared singleton.
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
    preamble: PREAMBLE,
    globalRules: GLOBAL_RULES,
  },
};
