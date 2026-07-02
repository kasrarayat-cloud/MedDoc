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
// Structured elements (feat/structured-templates, 2026-07-02) — the SAME
// schema the parse engine validates with (single source of truth), so a
// parsed structure always round-trips review → save → preview.
import { SectionStructureSchema } from '@/lib/note-template-parse/note-template-schema';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';
import { TEMPLATE_FIELD_LIMITS as LIM } from '@/lib/note-template-parse/note-template-schema';
import type {
  ParsedTemplateDraft,
  NoteTemplateSection,
} from '@/lib/note-template-parse/note-template-schema';

export const FormatHintSchema = z.enum(['prose', 'bullets', 'numbered']);

/** A section as the review UI submits it. NO defaultTextMode — it's derived
 *  (coerced) here, never accepted from the client. */
export const ReviewedSectionSchema = z
  .object({
    key: z.string().trim().min(1).max(LIM.key),
    label: z.string().trim().min(1).max(LIM.label),
    order: z.number().int().nonnegative(),
    formatHint: FormatHintSchema,
    styleInstructions: z.string().trim().max(LIM.styleInstructions).nullable().default(null),
    defaultText: z.string().max(LIM.defaultText).nullable().default(null),
    /** Table/option-set structure — carried through verbatim from the parse;
     *  the review UI displays it read-only in v1. Optional (prose sections). */
    structure: SectionStructureSchema.nullable().default(null),
  })
  .strict();

/** Doctor-level prose style. `.strict()` — no preamble/globalRules accepted. */
export const ReviewedStyleProfileSchema = z
  .object({
    tense: z.string().trim().max(LIM.tense).nullable().default(null),
    tone: z.string().trim().max(LIM.tone).default(''),
    abbreviations: z.string().trim().max(LIM.abbreviations).nullable().default(null),
  })
  .strict();

export const ReviewedTemplateSchema = z
  .object({
    /** Present when editing an existing template; absent for a brand-new one. */
    id: z.string().cuid().optional(),
    name: z.string().trim().min(1, 'Give your format a name').max(LIM.name),
    /** Matches the visit's specialty slug at generation time; null = applies to
     *  all of the doctor's visits (the catch-all). Constrained to the static
     *  specialty catalog: the parse LLM emits free-text encounter types
     *  ("Follow-up progress note") which can never equal a visit.specialty —
     *  persisting one produced a template that silently never applied
     *  (custom-template QA 2026-07-02, finding F-2). Server-side backstop for
     *  the review editor's catch-all coercion; the full static catalog (not
     *  the flag-filtered picker list) so flag flips never orphan saved rows. */
    encounterType: z
      .string()
      .trim()
      .min(1)
      .max(LIM.encounterType)
      .refine((v): v is (typeof SPECIALTY_IDS)[number] => (SPECIALTY_IDS as readonly string[]).includes(v), {
        message: 'Unknown encounter type — pick a specialty from the list or "All my visits".',
      })
      .nullable()
      .default(null),
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
      structure: s.structure ?? null,
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

// ── Friendly validation messaging ───────────────────────────────────────────
// The save action must never surface a raw Zod technical message (e.g. "Too
// big: expected string to have <=60 characters") to the doctor. This maps a
// ReviewedTemplateSchema failure to a clear, field-named sentence. Custom
// schema messages (e.g. "Give your format a name") pass through unchanged.

const TOP_FIELD_LABELS: Record<string, string> = {
  name: 'Format name',
  encounterType: 'Specialty',
  'styleProfile.tense': 'Writing tense',
  'styleProfile.tone': 'Writing tone',
  'styleProfile.abbreviations': 'Abbreviations',
};

function fieldLabel(path: ReadonlyArray<PropertyKey>): string {
  const p = path.map(String);
  if (p[0] === 'sections' && p.length >= 3) {
    const idx = Number(p[1]);
    const sub: Record<string, string> = {
      label: 'heading',
      key: 'key',
      styleInstructions: 'formatting note',
      defaultText: 'default text',
    };
    return `Section ${Number.isFinite(idx) ? idx + 1 : ''} ${sub[p[2]] ?? p[2]}`
      .replace(/\s+/g, ' ')
      .trim();
  }
  return TOP_FIELD_LABELS[p.join('.')] ?? TOP_FIELD_LABELS[p[p.length - 1]] ?? p[p.length - 1] ?? 'A field';
}

/** Map a ReviewedTemplateSchema failure to a doctor-friendly message — NEVER the
 *  raw Zod technical text. Branches on `issue.code` (stable API), not the
 *  message string (cosmetic + version-volatile), so a Zod wording change can't
 *  silently start leaking raw text. Use in place of `error.issues[0].message`. */
export function friendlyValidationError(error: z.ZodError): string {
  const issue = error.issues[0];
  if (!issue) return 'This format has fields we couldn’t accept — please review and try again.';
  const field = fieldLabel(issue.path);
  switch (issue.code) {
    case 'too_big':
      return `${field} is too long — please shorten it.`;
    case 'unrecognized_keys':
      // e.g. a crafted payload smuggling preamble/globalRules (.strict()).
      return 'This format has fields we couldn’t accept — please review and try again.';
    case 'too_small':
    case 'custom': {
      // The schema sets its own doctor-friendly message on these (e.g. "Give
      // your format a name", "Keep at least one section") — surface it, but
      // guard against a bare Zod default sneaking through.
      const raw = issue.message ?? '';
      return /^(too small|invalid|expected )/i.test(raw) ? `${field} is required.` : raw;
    }
    default:
      return `${field} isn’t valid — please review it.`;
  }
}
