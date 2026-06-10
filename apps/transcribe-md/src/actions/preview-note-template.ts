'use server';

// ============================================================================
// previewNoteTemplateAction — live sample-note preview for the review screen.
// ----------------------------------------------------------------------------
// Generates a sample SOAP note IN THE DOCTOR'S PARSED (not-yet-active) FORMAT so
// they see real output before activating. It REUSES the real generation path's
// pure primitives — buildSoapSystemPrompt + buildSoapUserPrompt (which carry
// the IMMUTABLE safety preamble + confirm-not-fabricate, sourced from the system
// default and un-weakenable by a custom template) + modelClient.completeText +
// validateSoapStructure — but DELIBERATELY does NOT call the L3-L6 layer
// wrappers, because those persist to a TranscribeVisit row. There is NO visit,
// NO patient, NO real PHI here: the ONLY input is the fixed synthetic transcript
// (SAMPLE_PREVIEW_*). The model call is logged with visitId:null (the same
// stateless posture as tm_template_parse), so the only DB rows produced are
// FK-less AiCall/ApiUsageEvent billing telemetry — never visit/PHI data.
//
// Generated once per distinct template content (Redis content-hash cache), not
// on every review-screen load. The preview is ADDITIVE: a failure here returns
// { ok:false } and MUST never block parse/activate (the UI handles it locally).
// ============================================================================

import { modelClient, wrapAsData } from '@meddoc/ai';

import { requireSession } from '@/lib/auth';
import {
  ReviewedTemplateSchema,
  normalizeReviewedTemplate,
  friendlyValidationError,
} from '@/lib/note-template-persist/reviewed-template';
import { applyPhiGate } from '@/lib/note-template-parse/phi-gate';
import {
  buildSoapSystemPrompt,
  buildSoapUserPrompt,
  normalizeTemplate,
  requiredSectionLabels,
} from '@/worker/note-templates/build-soap-prompt';
import { validateSoapStructure } from '@/worker/layers/soap-structure-validator';
import { specialtyGuidance } from '@/worker/prompts/specialty-guidance';
import {
  SAMPLE_PREVIEW_TRANSCRIPT,
  SAMPLE_PREVIEW_ENTITIES,
  SAMPLE_PREVIEW_SPECIALTY,
  SYNTHETIC_TRANSCRIPT_VERSION,
} from '@/worker/note-templates/sample-preview-transcript';
import {
  previewCacheKey,
  getCachedPreview,
  setCachedPreview,
} from '@/lib/sample-preview-cache';

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const PREVIEW_MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8';

export type PreviewTemplateResult =
  | { ok: true; markdown: string; cached: boolean }
  | { ok: false; error: string };

/**
 * Generate (or return cached) a sample SOAP note rendered in the reviewed
 * template's format, from the FIXED synthetic transcript. Never persists a
 * visit; never touches real PHI.
 */
export async function previewNoteTemplateAction(
  rawInput: unknown
): Promise<PreviewTemplateResult> {
  const session = await requireSession();

  // 1. Validate the reviewed draft (same schema as save) → friendly errors.
  const parsed = ReviewedTemplateSchema.safeParse(rawInput);
  if (!parsed.success) {
    return { ok: false, error: friendlyValidationError(parsed.error) };
  }

  // 2. Normalize (forces defaultTextMode coercion → scaffold_confirm markers,
  //    exactly as the save path does) + deterministic PHI re-scrub. If the
  //    doctor edited PHI into a structural field, refuse the preview (the save
  //    would refuse too) rather than render it.
  const { draft } = normalizeReviewedTemplate(parsed.data);
  const gate = applyPhiGate(draft, [], [], false);
  if (gate.rejected) {
    return { ok: false, error: gate.reason };
  }

  // 3. Cache by the scrubbed content (+ synthetic-transcript version). Pre-save
  //    drafts have no row/version, so this is the only stable "once per version"
  //    key; identical content (pre- or post-save) hits the same entry.
  const cacheKey = previewCacheKey(gate.template, SYNTHETIC_TRANSCRIPT_VERSION);
  const cached = await getCachedPreview(cacheKey);
  if (cached) {
    return { ok: true, markdown: cached, cached: true };
  }

  // 4. Build the REAL L4 prompt from the parsed template (immutable safety
  //    preamble + confirm-not-fabricate baked in by buildSoapSystemPrompt).
  const template = normalizeTemplate({
    id: 'tmpl_preview',
    version: 0,
    isSystemDefault: false,
    sections: gate.template.sections,
    styleProfile: gate.template.styleProfile,
  });

  const system = buildSoapSystemPrompt(template, {
    specialty: SAMPLE_PREVIEW_SPECIALTY,
    audioQualityAlert: null,
    interpreterAlert: null,
    specialtyGuidanceText: specialtyGuidance(SAMPLE_PREVIEW_SPECIALTY) || null,
  });
  const user = buildSoapUserPrompt({
    specialty: SAMPLE_PREVIEW_SPECIALTY,
    entitiesJson: JSON.stringify(SAMPLE_PREVIEW_ENTITIES, null, 2),
    wrappedTranscript: wrapAsData(SAMPLE_PREVIEW_TRANSCRIPT).wrapped,
  });

  // 5. Real model call — practiceId for billing telemetry, visitId:null (no
  //    visit, no FK). MOCK_AI_CALLS short-circuits to the canned fixture in CI.
  let markdown: string;
  try {
    const { text } = await modelClient.completeText({
      practiceId: session.user.practiceId,
      visitId: null,
      userId: session.user.id,
      purpose: 'tm_soap_draft',
      provider: 'anthropic',
      model: PREVIEW_MODEL,
      system,
      user,
      maxTokens: 8192,
      temperature: 0.2,
    });
    markdown = text;
  } catch (err) {
    console.error(
      '[preview-note-template] generation failed:',
      err instanceof Error ? err.message : err
    );
    return { ok: false, error: "Couldn't render a sample right now." };
  }

  if (!markdown?.trim()) {
    return { ok: false, error: "Couldn't render a sample right now." };
  }

  // Structure check is informational only — never block a preview on it (the
  // sample is the sample; validateSoapStructure never throws).
  validateSoapStructure(markdown, requiredSectionLabels(template));

  await setCachedPreview(cacheKey, markdown);
  return { ok: true, markdown, cached: false };
}
