// ============================================================================
// Layer 7f — Custom SOAP template fill (T-M24 + T-M24.smart)
// ----------------------------------------------------------------------------
// Runs in parallel with the other L7 automation layers, gated on the
// visit's templateId. Produces a JSON dict of token → content that the
// on-demand filled-docx endpoint merges with the template's binary via
// docxtemplater.
//
// T-M24.smart (Lever 1 + 2) — when the template was auto-injected,
// three of the 22 supported tokens are deterministic from the visit
// row (patient_name, patient_dob, visit_date) so we skip Claude for
// those and merge them into the fill result. Everything else (the 13
// clinical sub-sections + the primary SOAP + the pain-mgmt date-of-
// injury) goes through one Claude call as before.
//
// Template-fill failure NEVER fails the visit. A no-op return ({})
// leaves `filledTemplate` unset and the UI renders "template not
// available yet — retry." on the download button. Standard QuillMD
// outputs (SOAP, ICD codes, Rx, etc.) continue unaffected.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';

import { SUPPORTED_TOKENS } from '@/lib/template-tokens';

const MODEL = 'claude-sonnet-4-6';

// Tokens we fill deterministically from the visit/patient row. Never
// asked of Claude — both to save tokens and to guarantee they match
// the canonical record (no hallucinated dates or misspelled names).
const DETERMINISTIC_TOKENS = ['patient_name', 'patient_dob', 'visit_date'] as const;
type DeterministicToken = (typeof DETERMINISTIC_TOKENS)[number];

/** AI output schema — every supported token is optional. Claude is
 *  instructed to omit tokens for which no content exists in the visit;
 *  `.strip()` (the default) silently drops hallucinated keys so a
 *  stray extra key doesn't fail the whole fill. */
const TemplateFillOutput = z.object({
  // metadata
  patient_name: z.string().optional(),
  patient_dob: z.string().optional(),
  visit_date: z.string().optional(),
  date_of_injury: z.string().optional(),
  // primary SOAP
  chief_complaint: z.string().optional(),
  hpi: z.string().optional(),
  pmh: z.string().optional(),
  medications: z.string().optional(),
  allergies: z.string().optional(),
  ros: z.string().optional(),
  exam: z.string().optional(),
  assessment: z.string().optional(),
  plan: z.string().optional(),
  // clinical sub-sections (Lever 2)
  current_status: z.string().optional(),
  prior_injuries: z.string().optional(),
  social_history: z.string().optional(),
  family_history: z.string().optional(),
  past_surgical_history: z.string().optional(),
  imaging: z.string().optional(),
  general_exam: z.string().optional(),
  heent: z.string().optional(),
  lumbar_spine: z.string().optional(),
  right_lower_extremity: z.string().optional(),
  left_lower_extremity: z.string().optional(),
  reflexes: z.string().optional(),
  integument: z.string().optional(),
});
export type TemplateFillOutput = z.infer<typeof TemplateFillOutput>;

export interface Layer7fInput {
  visitId: string;
  practiceId: string;
  templateId: string;
  soapFinal: string;
  transcriptText: string | null;
}

export async function runLayer7fTemplateFill(
  input: Layer7fInput
): Promise<TemplateFillOutput> {
  const [template, visit] = await Promise.all([
    prisma.transcribeTemplate.findUnique({
      where: { id: input.templateId },
      select: {
        id: true,
        name: true,
        extractedText: true,
        tokens: true,
        deletedAt: true,
        // Smart-mode discriminator: non-null means the upload injector
        // wrote placeholders into the binary, so we fill from all 22
        // SUPPORTED_TOKENS rather than from `tokens` (hand-written).
        injectedMinioKey: true,
      },
    }),
    prisma.transcribeVisit.findUnique({
      where: { id: input.visitId },
      select: {
        patientName: true,
        createdAt: true,
        patient: {
          select: { name: true, dateOfBirth: true },
        },
      },
    }),
  ]);

  // Template went away between visit creation and now. No-op + don't
  // throw — a missing template shouldn't block the rest of the visit.
  if (!template || template.deletedAt !== null) {
    return {};
  }
  if (!visit) {
    // Visit disappeared between the outer worker's lookup and ours.
    // Shouldn't happen in practice; exit clean.
    return {};
  }

  const isSmartMode = template.injectedMinioKey !== null;
  const supportedSet = new Set<string>(SUPPORTED_TOKENS);
  const tokensInDoc = isSmartMode ? [...SUPPORTED_TOKENS] : template.tokens;
  const supportedTokensUsed: string[] = tokensInDoc.filter((t: string) =>
    supportedSet.has(t)
  );
  if (supportedTokensUsed.length === 0) {
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: { filledTemplate: '{}' },
    });
    return {};
  }

  // Split tokens: deterministic (filled from visit row) vs AI.
  const determSet = new Set<string>(DETERMINISTIC_TOKENS);
  const deterministicRequested = supportedTokensUsed.filter((t) =>
    determSet.has(t)
  ) as DeterministicToken[];
  const aiRequested = supportedTokensUsed.filter((t) => !determSet.has(t));

  const deterministicFill = buildDeterministicFill(
    deterministicRequested,
    visit
  );

  // No AI tokens → short-circuit. Rare but possible (e.g. a template
  // containing only Patient: / DOB: / visit date lines).
  if (aiRequested.length === 0) {
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: { filledTemplate: JSON.stringify(deterministicFill) },
    });
    return deterministicFill;
  }

  const system = [
    "You are an AI medical scribe filling a doctor's personal clinical",
    'template. Produce concise, clinically-accurate content for each',
    'requested token — derived ONLY from the provided visit material,',
    'no invention.',
    '',
    'RULES:',
    '1. Every value must be plain text. No markdown, no leading or',
    '   trailing newlines, no bullet characters (the template\'s own',
    '   formatting handles structure).',
    '2. If a token has no relevant content in the visit, OMIT it from',
    '   the JSON — do NOT write "N/A", "[not documented]", "-", or an',
    '   empty string. The template renders missing slots as empty at',
    '   the docxtemplater stage.',
    '3. Match the clinical voice of the polished SOAP note (past',
    '   tense, professional, patient-neutral). Do not quote the',
    '   transcript verbatim; summarise in clinical style.',
    '4. For sub-section tokens (e.g. right_lower_extremity,',
    '   lumbar_spine, general_exam, reflexes), pull only the matching',
    '   physical-exam content — do not duplicate the full exam across',
    '   multiple sub-tokens. If the visit did not examine that body',
    '   region, OMIT the token.',
    '5. date_of_injury: a date the doctor mentions as the time of',
    '   injury / accident (common in pain-management / workers-comp',
    '   letters). Format as MM/DD/YYYY. Omit the token if the visit',
    '   did not involve an injury or no date was mentioned.',
    '6. Return VALID JSON ONLY. No markdown fences, no prose around',
    '   the JSON.',
  ].join('\n');

  const user = [
    "Doctor's template (structural context — shows section headings",
    'and flow, but the tokens are what you fill):',
    '',
    template.extractedText,
    '',
    `Tokens to fill (return these keys as JSON string values — omit any with no content): ${aiRequested.join(', ')}`,
    '',
    'Visit SOAP note (final polished output, your primary source):',
    '',
    input.soapFinal,
    '',
    'Raw transcript (secondary source — use for detail the SOAP may',
    "have abbreviated; don't paraphrase verbatim):",
    '',
    input.transcriptText ?? '(transcript not available)',
    '',
    'Return the filled JSON now:',
  ].join('\n');

  const aiFill = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_template_fill',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: TemplateFillOutput,
    maxTokens: 4096,
  });

  // Merge — deterministic values always win (canonical record; Claude
  // should not be inventing patient names or visit dates even if we
  // accidentally asked).
  const merged: TemplateFillOutput = { ...aiFill, ...deterministicFill };

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { filledTemplate: JSON.stringify(merged) },
  });

  return merged;
}

/** Format a Date as "MM/DD/YYYY" — matches the template's DOB format
 *  (Dr M's template shows "07/12/1998"). */
function formatDobSlash(d: Date): string {
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const yyyy = String(d.getUTCFullYear());
  return `${mm}/${dd}/${yyyy}`;
}

/** Format a Date as "March 3, 2026" — matches the consultation-letter
 *  visit-date layout. Locale-independent (month names hard-coded) so
 *  different server locales don't produce drift. */
function formatVisitDateLong(d: Date): string {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  return `${months[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

interface VisitForFill {
  patientName: string | null;
  createdAt: Date;
  patient: { name: string; dateOfBirth: Date | null } | null;
}

function buildDeterministicFill(
  requested: DeterministicToken[],
  visit: VisitForFill
): Partial<TemplateFillOutput> {
  const out: Partial<TemplateFillOutput> = {};
  if (requested.includes('patient_name')) {
    const name = visit.patient?.name ?? visit.patientName;
    if (name) out.patient_name = name;
  }
  if (requested.includes('patient_dob') && visit.patient?.dateOfBirth) {
    out.patient_dob = formatDobSlash(visit.patient.dateOfBirth);
  }
  if (requested.includes('visit_date')) {
    out.visit_date = formatVisitDateLong(visit.createdAt);
  }
  return out;
}
