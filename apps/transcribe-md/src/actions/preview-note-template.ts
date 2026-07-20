"use server";

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

import { modelClient, wrapAsData } from "@meddoc/ai";

import { requireSession } from "@/lib/auth";
import {
  claimCurrentLegacyNoteTemplateProviderActor,
  LegacyNoteTemplateProviderAuthorityError,
  type LegacyNoteTemplateProviderAuthorityClaim,
} from "@/lib/note-template-parse/parse-note-to-template";
import {
  ReviewedTemplateSchema,
  normalizeReviewedTemplate,
  friendlyValidationError,
} from "@/lib/note-template-persist/reviewed-template";
import { applyPhiGate } from "@/lib/note-template-parse/phi-gate";
import {
  hasLocallyUnsafeReviewedTemplateContent,
  REVIEWED_TEMPLATE_PRIVACY_REJECTION,
} from "@/lib/note-template-parse/reviewed-template-safety";
import type {
  NoteTemplateSection,
  ParsedTemplateDraft,
} from "@/lib/note-template-parse/note-template-schema";
import {
  buildSoapSystemPrompt,
  buildSoapUserPrompt,
  normalizeTemplate,
  requiredSectionLabels,
} from "@/worker/note-templates/build-soap-prompt";
import { validateSoapStructure } from "@/worker/layers/soap-structure-validator";
import { specialtyGuidance } from "@/worker/prompts/specialty-guidance";
import {
  SAMPLE_PREVIEW_TRANSCRIPT,
  SAMPLE_PREVIEW_ENTITIES,
  SAMPLE_PREVIEW_SPECIALTY,
  SYNTHETIC_TRANSCRIPT_VERSION,
} from "@/worker/note-templates/sample-preview-transcript";
import {
  previewCacheKey,
  getCachedPreview,
  setCachedPreview,
} from "@/lib/sample-preview-cache";

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const PREVIEW_MODEL =
  process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-opus-4-8";

export type PreviewTemplateResult =
  | { ok: true; markdown: string; cached: boolean }
  | { ok: false; error: string; privacyRejected?: true };

interface ProviderSafePreviewProjection {
  readonly draft: ParsedTemplateDraft;
  restore(markdown: string): string;
}

/**
 * Provider-visible preview projection. Every physician-authored string is
 * replaced with a stable structural token; the provider sees only shape plus
 * the repository-owned synthetic visit. Tokens are restored locally after the
 * post-response authority fence, and only tokenized markdown is cached.
 */
function providerSafePreviewProjection(
  source: ParsedTemplateDraft,
): ProviderSafePreviewProjection {
  const replacements: Array<readonly [string, string]> = [];
  const sections: NoteTemplateSection[] = source.sections.map(
    (section, index) => {
      const sectionToken = `QMD_SECTION_${String(index + 1).padStart(3, "0")}`;
      replacements.push([sectionToken, section.label]);
      let structure: NoteTemplateSection["structure"] = null;
      if (section.structure?.kind === "options") {
        structure = {
          kind: "options",
          multi: section.structure.multi,
          options: section.structure.options.map((option, optionIndex) => {
            const token = `QMD_OPTION_${String(index + 1).padStart(3, "0")}_${String(optionIndex + 1).padStart(3, "0")}`;
            replacements.push([token, option]);
            return token;
          }),
        };
      } else if (section.structure?.kind === "table") {
        structure = {
          kind: "table",
          columns: section.structure.columns.map((column, columnIndex) => {
            const token = `QMD_COLUMN_${String(index + 1).padStart(3, "0")}_${String(columnIndex + 1).padStart(3, "0")}`;
            replacements.push([token, column]);
            return token;
          }),
          ...(section.structure.rowLabels
            ? {
                rowLabels: section.structure.rowLabels.map((row, rowIndex) => {
                  const token = `QMD_ROW_${String(index + 1).padStart(3, "0")}_${String(rowIndex + 1).padStart(3, "0")}`;
                  replacements.push([token, row]);
                  return token;
                }),
              }
            : {}),
        };
      }
      return {
        key: `qmd_section_${index + 1}`,
        label: sectionToken,
        order: index + 1,
        formatHint: section.formatHint,
        styleInstructions: null,
        defaultText: null,
        defaultTextMode: "omit_unless_supported",
        structure,
      };
    },
  );
  const draft: ParsedTemplateDraft = {
    name: "QuillMD synthetic format preview",
    encounterType: null,
    sections,
    styleProfile: {
      tense: null,
      tone: "professional clinical",
      abbreviations: null,
      contextDefaults: null,
    },
  };
  return {
    draft,
    restore(markdown) {
      return [...replacements]
        .sort(([left], [right]) => right.length - left.length)
        .reduce(
          (value, [token, original]) => value.split(token).join(original),
          markdown,
        );
    },
  };
}

/**
 * Generate (or return cached) a sample SOAP note rendered in the reviewed
 * template's format, from the FIXED synthetic transcript. Never persists a
 * visit; never touches real PHI.
 */
export async function previewNoteTemplateAction(
  rawInput: unknown,
): Promise<PreviewTemplateResult> {
  const session = await requireSession();

  let initialActor: LegacyNoteTemplateProviderAuthorityClaim;
  try {
    initialActor = await claimCurrentLegacyNoteTemplateProviderActor({
      actorUserId: session.user.id,
    });
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return {
        ok: false,
        error:
          "Current physician access could not be confirmed. No sample was generated.",
      };
    }
    throw error;
  }

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
  if (hasLocallyUnsafeReviewedTemplateContent(draft)) {
    return {
      ok: false,
      error: REVIEWED_TEMPLATE_PRIVACY_REJECTION,
      privacyRejected: true,
    };
  }
  const gate = applyPhiGate(draft, [], [], false);
  if (gate.rejected) {
    return { ok: false, error: gate.reason, privacyRejected: true };
  }

  const projection = providerSafePreviewProjection(gate.template);

  // 3. Cache only the provider-safe structural projection (+ synthetic input
  //    version). No physician-authored string enters the key payload or value.
  const cacheKey = previewCacheKey(
    projection.draft,
    SYNTHETIC_TRANSCRIPT_VERSION,
  );
  const cached = await getCachedPreview(cacheKey);
  if (cached) {
    try {
      await claimCurrentLegacyNoteTemplateProviderActor({
        actorUserId: initialActor.actorUserId,
        expectedPracticeId: initialActor.practiceId,
      });
    } catch (error) {
      if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
        return {
          ok: false,
          error:
            "Current physician access changed while the sample was loaded. No sample was returned.",
        };
      }
      throw error;
    }
    return { ok: true, markdown: projection.restore(cached), cached: true };
  }

  // 4. Build the REAL L4 prompt from the parsed template (immutable safety
  //    preamble + confirm-not-fabricate baked in by buildSoapSystemPrompt).
  const template = normalizeTemplate({
    id: "tmpl_preview",
    version: 0,
    isSystemDefault: false,
    sections: projection.draft.sections,
    styleProfile: projection.draft.styleProfile,
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
    const providerActor = await claimCurrentLegacyNoteTemplateProviderActor({
      actorUserId: initialActor.actorUserId,
      expectedPracticeId: initialActor.practiceId,
    });
    const beforeProviderAttempt = async () => {
      const current = await claimCurrentLegacyNoteTemplateProviderActor({
        actorUserId: providerActor.actorUserId,
        expectedPracticeId: providerActor.practiceId,
      });
      if (
        current.actorUserId !== providerActor.actorUserId ||
        current.practiceId !== providerActor.practiceId
      ) {
        throw new LegacyNoteTemplateProviderAuthorityError();
      }
    };
    const afterProviderAttempt = async () => {
      const current = await claimCurrentLegacyNoteTemplateProviderActor({
        actorUserId: providerActor.actorUserId,
        expectedPracticeId: providerActor.practiceId,
      });
      if (
        current.actorUserId !== providerActor.actorUserId ||
        current.practiceId !== providerActor.practiceId
      ) {
        throw new LegacyNoteTemplateProviderAuthorityError();
      }
    };
    const { text } = await modelClient.completeText({
      practiceId: providerActor.practiceId,
      visitId: null,
      userId: providerActor.actorUserId,
      purpose: "tm_soap_draft",
      provider: "anthropic",
      model: PREVIEW_MODEL,
      system,
      user,
      maxTokens: 8192,
      temperature: 0.2,
      beforeProviderAttempt,
      afterProviderAttempt,
    });
    await claimCurrentLegacyNoteTemplateProviderActor({
      actorUserId: providerActor.actorUserId,
      expectedPracticeId: providerActor.practiceId,
    });
    markdown = text;
  } catch (err) {
    if (err instanceof LegacyNoteTemplateProviderAuthorityError) {
      return {
        ok: false,
        error:
          "Current physician access changed while the sample was generated. No sample was returned.",
      };
    }
    console.error(
      "[preview-note-template] generation failed:",
      err instanceof Error ? err.message : err,
    );
    return { ok: false, error: "Couldn't render a sample right now." };
  }

  if (!markdown?.trim()) {
    return { ok: false, error: "Couldn't render a sample right now." };
  }

  // Structure check is informational only — never block a preview on it (the
  // sample is the sample; validateSoapStructure never throws).
  validateSoapStructure(markdown, requiredSectionLabels(template));

  // Final current-authority fence must precede every observable side effect.
  // A revoked actor receives no result and must not populate the shared cache.
  try {
    await claimCurrentLegacyNoteTemplateProviderActor({
      actorUserId: initialActor.actorUserId,
      expectedPracticeId: initialActor.practiceId,
    });
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return {
        ok: false,
        error:
          "Current physician access changed before the sample could be returned. No sample was returned.",
      };
    }
    throw error;
  }
  await setCachedPreview(cacheKey, markdown);
  return { ok: true, markdown: projection.restore(markdown), cached: false };
}
