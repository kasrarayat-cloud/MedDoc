import { z } from 'zod';

import { SemanticMappingSchema } from './ir';
import { TemplateTwinFieldIntentInputSchema } from './field-intent';

export const TemplateTwinUpdateMappingsRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    expectedFieldIntentsSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    mappings: z.array(SemanticMappingSchema).min(1).max(500),
    fieldIntents: z
      .array(TemplateTwinFieldIntentInputSchema)
      .max(500)
      .refine(
        (intents) =>
          new Set(intents.map((intent) => intent.fieldId)).size ===
          intents.length,
        { message: 'Each field may have only one requested intent.' },
      )
      .optional(),
  })
  .strict();

export const TemplateTwinSyntheticTestRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    expectedFieldIntentsSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    encounterText: z.string().trim().min(10).max(12_000),
  })
  .strict();

export const TemplateTwinCertifyRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    expectedFieldIntentsSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    expectedSyntheticTestProvenanceSha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/),
    acknowledgeStructure: z.literal(true),
    acknowledgeSyntheticOutput: z.literal(true),
    optionalFieldWaivers: z
      .array(
        z
          .object({
            fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/),
            reason: z.string().trim().min(10).max(500),
          })
          .strict(),
      )
      .max(500)
      .default([])
      .refine(
        (waivers) =>
          new Set(waivers.map((waiver) => waiver.fieldId)).size ===
          waivers.length,
        { message: 'Each optional field may be waived only once.' },
      ),
  })
  .strict();

export const TemplateTwinCorrectionReasonSchema = z.enum([
  'physician_review_correction',
  'transcript_correction',
  'selected_exact_option',
  'clarified_checkbox',
  'clarified_number_or_unit',
  'corrected_laterality',
  'corrected_medication',
  'corrected_allergy',
]);

export const TemplateTwinFieldCorrectionRequestSchema = z
  .object({
    expectedManifestVersion: z.number().int().positive(),
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/),
    value: z.union([
      z.string().max(10_000),
      z.number().finite(),
      z.boolean(),
      z.array(z.string().max(1_000)).max(100),
      z.array(z.record(z.string(), z.string().max(1_000).nullable())).max(100),
      z.null(),
    ]),
    sourceFactIds: z
      .array(z.string().regex(/^ttfact_[a-f0-9]{24}$/))
      .max(100)
      .refine((ids) => new Set(ids).size === ids.length, {
        message: 'Source fact IDs must be unique.',
      }),
    reasonCode: TemplateTwinCorrectionReasonSchema,
    createMappingRule: z.boolean(),
  })
  .strict();

export const TemplateTwinReviewAcknowledgementRequestSchema = z
  .object({
    expectedManifestVersion: z.number().int().positive(),
    expectedManifestSha256: z.string().regex(/^[a-f0-9]{64}$/),
  })
  .strict();

export type TemplateTwinUpdateMappingsRequest = z.infer<
  typeof TemplateTwinUpdateMappingsRequestSchema
>;
export type TemplateTwinCertifyRequest = z.infer<
  typeof TemplateTwinCertifyRequestSchema
>;
export type TemplateTwinFieldCorrectionRequest = z.infer<
  typeof TemplateTwinFieldCorrectionRequestSchema
>;
export type TemplateTwinReviewAcknowledgementRequest = z.infer<
  typeof TemplateTwinReviewAcknowledgementRequestSchema
>;
