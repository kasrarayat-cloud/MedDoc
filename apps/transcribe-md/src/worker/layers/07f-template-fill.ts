// ============================================================================
// Layer 7f — Custom SOAP template fill (T-M24)
// ----------------------------------------------------------------------------
// Runs in parallel with the other L7 automation layers, gated on the
// visit's templateId. Claude takes the polished SOAP + raw transcript
// + the doctor's template text and produces a JSON dict of
// token → content. The on-demand filled-docx endpoint merges this
// dict with the template's binary via docxtemplater.
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

/** AI output schema — every supported token is optional, since Claude
 *  is instructed to omit tokens for which no content exists in the
 *  visit. Extra keys Claude invents are stripped by `.strict()` at
 *  the Zod layer and would trigger a SCHEMA_FAIL; `.strip()` (the
 *  default) silently drops them, which is what we want so a stray
 *  hallucinated key doesn't fail the whole fill. */
const TemplateFillOutput = z.object({
  chief_complaint: z.string().optional(),
  hpi: z.string().optional(),
  pmh: z.string().optional(),
  medications: z.string().optional(),
  allergies: z.string().optional(),
  ros: z.string().optional(),
  exam: z.string().optional(),
  assessment: z.string().optional(),
  plan: z.string().optional(),
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
  const template = await prisma.transcribeTemplate.findUnique({
    where: { id: input.templateId },
    select: {
      id: true,
      name: true,
      extractedText: true,
      tokens: true,
      deletedAt: true,
      // T-M24.smart — when the upload endpoint auto-injected tokens,
      // the injected tokens aren't in `tokens` (that field only
      // captures hand-written {{tokens}} in the original). We detect
      // smart-mode by checking whether an injected variant exists.
      injectedMinioKey: true,
    },
  });

  // Template went away between visit creation and now. No-op + don't
  // throw — a missing template shouldn't block the rest of the visit.
  if (!template || template.deletedAt !== null) {
    return {};
  }

  // When the template was auto-injected, the tokens the fill layer
  // should target are the 9 SUPPORTED_TOKENS (Claude produces content
  // for any subset that's relevant to the visit). The detector only
  // injects placeholders for clinical_narrative sections that mapped
  // to a token, so asking for all 9 is safe — extras get silently
  // dropped by docxtemplater.
  const supportedSet = new Set<string>(SUPPORTED_TOKENS);
  const tokensInDoc = template.injectedMinioKey
    ? [...SUPPORTED_TOKENS]
    : template.tokens;
  const supportedTokensUsed: string[] = tokensInDoc.filter((t: string) =>
    supportedSet.has(t)
  );
  if (supportedTokensUsed.length === 0) {
    // Template has no known tokens — nothing for us to fill. Still
    // record an empty `{}` so the skip-check correctly reports L7f
    // as complete and BullMQ retries don't re-invoke Claude for a
    // no-op.
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: { filledTemplate: '{}' },
    });
    return {};
  }

  const system = [
    'You are an AI medical scribe filling a doctor\'s personal SOAP',
    'template. Produce concise, clinically-accurate content for each',
    'requested token — derived ONLY from the provided visit material,',
    'no invention.',
    '',
    'RULES:',
    '1. Every value must be plain text. No markdown, no leading/',
    '   trailing newlines, no bullet characters (the template\'s own',
    '   formatting handles structure).',
    '2. If a token has no relevant content in the visit, OMIT it from',
    '   the JSON — do NOT write "N/A", "[not documented]", "-", or an',
    '   empty string. The template fills missing slots with empty at',
    '   the docxtemplater stage.',
    '3. Match the clinical voice of the polished SOAP note (past',
    '   tense, professional, patient-neutral). Do not quote the',
    '   transcript verbatim; summarise in SOAP style.',
    '4. Return VALID JSON ONLY. No markdown fences, no prose around',
    '   the JSON.',
  ].join('\n');

  const user = [
    'Doctor\'s template (structural context — shows section headings',
    'and flow, but the tokens are what you fill):',
    '',
    template.extractedText,
    '',
    `Tokens to fill (return these keys as JSON string values — omit any with no content): ${supportedTokensUsed.join(', ')}`,
    '',
    'Visit SOAP note (final polished output, your primary source):',
    '',
    input.soapFinal,
    '',
    'Raw transcript (secondary source — use for detail the SOAP may',
    'have abbreviated; don\'t paraphrase verbatim):',
    '',
    input.transcriptText ?? '(transcript not available)',
    '',
    'Return the filled JSON now:',
  ].join('\n');

  const filled = await modelClient.complete({
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

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { filledTemplate: JSON.stringify(filled) },
  });

  return filled;
}
