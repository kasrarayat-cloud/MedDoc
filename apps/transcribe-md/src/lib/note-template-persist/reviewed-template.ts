// ============================================================================
// Note-format customization — Phase 2b: reviewed-template validation + normalize
// ----------------------------------------------------------------------------
// Pure (no 'use server', no Prisma) so it's unit-testable. Validates the
// template a doctor submits from the review screen and normalizes it into a
// PHI-gateable draft + the JSONB shapes persisted on note_templates.
//
// TWO SAFETY RULES ENFORCED IN CODE (not trusted from the client):
//   1. styleProfile accepts ONLY { tense, tone, abbreviations }. A custom
//      template can NEVER carry `preamble` / `globalRules` — the immutable
//      safety layer is sourced at generation time from the canonical system
//      default (build-soap-prompt), never from a custom row. `.strict()`
//      rejects any extra key, so a crafted payload can't smuggle a preamble.
//   2. defaultTextMode is COERCED: a non-empty default → `scaffold_confirm`
//      (gets the L5 confirm marker → normals-scrutiny applies); an empty
//      default → `omit_unless_supported`. `always_include` (which would skip
//      the confirm marker) is NEVER produced for a custom template.
// ============================================================================

import { z } from 'zod';
import type {
  ParsedTemplateDraft,
  NoteTemplateSection,
} from '@/lib/note-template-parse/note-template-schema';

export const FormatHintSchema = z.enum(['prose', 'bullets', 'numbered']);

/** A section as the review UI submits it. NO defaultTextMode — it's derived
 *  (coerced) here, never accepted from the client. */
export const ReviewedSectionSchema = z
  .object({
    key: z.string().trim().min(1).max(80),
    label: z.string().trim().min(1).max(120),
    order: z.number().int().nonnegative(),
    formatHint: FormatHintSchema,
    styleInstructions: z.string().trim().max(2000).nullable().default(null),
    defaultText: z.string().max(8000).nullable().default(null),
  })
  .strict();

/** Doctor-level prose style. `.strict()` — no preamble/globalRules accepted. */
export const ReviewedStyleProfileSchema = z
  .object({
    tense: z.string().trim().max(60).nullable().default(null),
    tone: z.string().trim().max(120).default(''),
    abbreviations: z.string().trim().max(200).nullable().default(null),
  })
  .strict();

export const ReviewedTemplateSchema = z
  .object({
    /** Present when editing an existing template; absent for a brand-new one. */
    id: z.string().cuid().optional(),
    name: z.string().trim().min(1, 'Give your format a name').max(120),
    /** Matches the visit's specialty slug at generation time; null = applies to
     *  all of the doctor's visits (the catch-all). */
    encounterType: z.string().trim().min(1).max(80).nullable().default(null),
    sections: z.array(ReviewedSectionSchema).min(1, 'Keep at least one section').max(40),
    styleProfile: ReviewedStyleProfileSchema,
  })
  .strict();

export type ReviewedTemplateInput = z.infer<typeof ReviewedTemplateSchema>;

/** Normalize a validated review submission into:
 *   - `draft`: a ParsedTemplateDraft (fed to the deterministic PHI gate);
 *   - the section/styleProfile JSON to persist (after the gate scrubs it).
 *  Re-numbers `order` to 1..n by the submitted order and COERCES
 *  defaultTextMode (rule 2 above). */
export function normalizeReviewedTemplate(input: ReviewedTemplateInput): {
  draft: ParsedTemplateDraft;
} {
  const ordered = [...input.sections].sort((a, b) => a.order - b.order);
  const sections: NoteTemplateSection[] = ordered.map((s, i) => {
    const trimmedDefault = s.defaultText?.trim() ? s.defaultText.trim() : null;
    return {
      key: s.key,
      label: s.label,
      order: i + 1,
      formatHint: s.formatHint,
      styleInstructions: s.styleInstructions?.trim() ? s.styleInstructions.trim() : null,
      defaultText: trimmedDefault,
      // RULE 2 — never always_include; a default is always confirm-gated.
      defaultTextMode: trimmedDefault ? 'scaffold_confirm' : 'omit_unless_supported',
    };
  });

  const draft: ParsedTemplateDraft = {
    name: input.name,
    encounterType: input.encounterType,
    sections,
    // RULE 1 — only the three prose-style fields; no safety fields exist here.
    styleProfile: {
      tense: input.styleProfile.tense,
      tone: input.styleProfile.tone,
      abbreviations: input.styleProfile.abbreviations,
    },
  };
  return { draft };
}
