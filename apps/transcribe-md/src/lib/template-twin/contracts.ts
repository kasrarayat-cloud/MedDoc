import { z } from 'zod';

import { SemanticMappingSchema } from './ir';

export const TemplateTwinUpdateMappingsRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    mappings: z.array(SemanticMappingSchema).min(1).max(500),
  })
  .strict();

export const TemplateTwinSyntheticTestRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    encounterText: z.string().trim().min(10).max(12_000),
  })
  .strict();

export const TemplateTwinCertifyRequestSchema = z
  .object({
    expectedMappingsSha256: z.string().regex(/^[a-f0-9]{64}$/),
    acknowledgeStructure: z.literal(true),
    acknowledgeSyntheticOutput: z.literal(true),
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

export type TemplateTwinUpdateMappingsRequest = z.infer<
  typeof TemplateTwinUpdateMappingsRequestSchema
>;
export type TemplateTwinFieldCorrectionRequest = z.infer<
  typeof TemplateTwinFieldCorrectionRequestSchema
>;
