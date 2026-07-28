import { createHash } from 'node:crypto';

import { z } from 'zod';

import {
  CertifiedTemplateFieldSpecificationSchema,
  TemplateFieldSpecificationContentSchema,
  computeTemplateFieldSpecificationContentSha256,
  computeTemplateFieldSyntheticCoverageSha256,
  deriveCustomConceptId,
  type CertifiedTemplateFieldSpecification,
  type TemplateFieldSpecificationContent,
} from './custom-concepts';
import { canonicalSha256 } from './canonical';
import type { TemplateField } from './ir';
import { isSupportedTemplateTwinConcept } from './supported-concepts';

export const TEMPLATE_TWIN_FIELD_INTENT_CONTRACT_VERSION =
  'template-twin-field-intent/1.0.0' as const;

export const TemplateTwinFieldIntentKindSchema = z.enum([
  'unresolved',
  'supported_concept',
  'static',
  'custom_concept',
]);
export type TemplateTwinFieldIntentKind = z.infer<
  typeof TemplateTwinFieldIntentKindSchema
>;

const FieldIdSchema = z.string().regex(/^ttf_[a-f0-9]{24}$/);

export const TemplateTwinFieldIntentInputSchema = z.discriminatedUnion(
  'intentKind',
  [
    z
      .object({
        fieldId: FieldIdSchema,
        intentKind: z.literal('unresolved'),
      })
      .strict(),
    z
      .object({
        fieldId: FieldIdSchema,
        intentKind: z.literal('supported_concept'),
        supportedConcept: z.string().trim().min(1).max(160),
      })
      .strict(),
    z
      .object({
        fieldId: FieldIdSchema,
        intentKind: z.literal('static'),
        reason: z.string().trim().min(10).max(500),
      })
      .strict(),
    z
      .object({
        fieldId: FieldIdSchema,
        intentKind: z.literal('custom_concept'),
        customSpec: TemplateFieldSpecificationContentSchema,
      })
      .strict(),
  ],
);
export type TemplateTwinFieldIntentInput = z.infer<
  typeof TemplateTwinFieldIntentInputSchema
>;

export interface TemplateTwinFieldIntentView {
  readonly intentKind: TemplateTwinFieldIntentKind;
  readonly decisionId: string | null;
  readonly version: number | null;
  readonly supportedConcept: string | null;
  readonly customConceptId: string | null;
  readonly customSpec: CertifiedTemplateFieldSpecification | null;
  readonly reason: string | null;
  readonly decidedAtIso: string | null;
  readonly lockedInVersion: boolean;
}

export interface PersistedTemplateTwinFieldIntent {
  readonly id: string;
  readonly fieldDefinitionId: string;
  readonly fieldId: string;
  readonly version: number;
  readonly intentKind: string;
  readonly supportedConcept: string | null;
  readonly customConceptId: string | null;
  readonly customSpec: unknown;
  readonly customSpecSha256: string | null;
  readonly reason: string | null;
  readonly decidedById: string;
  readonly decidedAt: Date;
}

export function fieldRequiresExplicitIntent(field: TemplateField): boolean {
  return field.rendererBinding.bindingType === 'ordinary_placeholder';
}

export function unresolvedFieldIntent(): TemplateTwinFieldIntentView {
  return {
    intentKind: 'unresolved',
    decisionId: null,
    version: null,
    supportedConcept: null,
    customConceptId: null,
    customSpec: null,
    reason: null,
    decidedAtIso: null,
    lockedInVersion: false,
  };
}

export function parsePersistedFieldIntent(
  row: PersistedTemplateTwinFieldIntent,
): TemplateTwinFieldIntentView {
  if (row.intentKind === 'SUPPORTED_CONCEPT') {
    if (!row.supportedConcept || !isSupportedTemplateTwinConcept(row.supportedConcept)) {
      throw new Error('Persisted Template Twin supported-concept intent is invalid.');
    }
    return {
      intentKind: 'supported_concept',
      decisionId: row.id,
      version: row.version,
      supportedConcept: row.supportedConcept,
      customConceptId: null,
      customSpec: null,
      reason: row.reason,
      decidedAtIso: row.decidedAt.toISOString(),
      lockedInVersion: true,
    };
  }
  if (row.intentKind === 'STATIC') {
    return {
      intentKind: 'static',
      decisionId: row.id,
      version: row.version,
      supportedConcept: null,
      customConceptId: null,
      customSpec: null,
      reason: row.reason,
      decidedAtIso: row.decidedAt.toISOString(),
      lockedInVersion: true,
    };
  }
  if (row.intentKind === 'CUSTOM_CONCEPT') {
    const customSpec = CertifiedTemplateFieldSpecificationSchema.parse(
      row.customSpec,
    );
    if (
      row.customConceptId !== customSpec.conceptId ||
      row.customSpecSha256 !==
        computeTemplateFieldSpecificationContentSha256(customSpec)
    ) {
      throw new Error('Persisted Template Twin custom-concept intent is invalid.');
    }
    return {
      intentKind: 'custom_concept',
      decisionId: row.id,
      version: row.version,
      supportedConcept: null,
      customConceptId: row.customConceptId,
      customSpec,
      reason: row.reason,
      decidedAtIso: row.decidedAt.toISOString(),
      lockedInVersion: true,
    };
  }
  throw new Error('Persisted Template Twin field intent kind is invalid.');
}

export function certifyCustomFieldSpecification(input: {
  content: TemplateFieldSpecificationContent;
  templateLineageId: string;
  compiledVersionId: string;
  fieldId: string;
  physicianUserId: string;
  certifiedAt: Date;
}): CertifiedTemplateFieldSpecification {
  const expectedConceptId = deriveCustomConceptId({
    templateLineageId: input.templateLineageId,
    compiledVersionId: input.compiledVersionId,
    fieldId: input.fieldId,
  });
  const content = TemplateFieldSpecificationContentSchema.parse({
    ...input.content,
    templateLineageId: input.templateLineageId,
    compiledVersionId: input.compiledVersionId,
    fieldId: input.fieldId,
    conceptId: expectedConceptId,
  });
  return CertifiedTemplateFieldSpecificationSchema.parse({
    ...content,
    certification: {
      status: 'certified',
      certifiedByUserId: input.physicianUserId,
      certifiedAt: input.certifiedAt.toISOString(),
      contentSha256: computeTemplateFieldSpecificationContentSha256(content),
      syntheticCoverageSha256:
        computeTemplateFieldSyntheticCoverageSha256(content),
    },
  });
}

function reasonSha256(reason: string | null): string | null {
  return reason === null
    ? null
    : createHash('sha256').update(reason, 'utf8').digest('hex');
}

export function templateTwinFieldIntentsSha256(
  fields: ReadonlyArray<{
    fieldId: string;
    intent: TemplateTwinFieldIntentView;
  }>,
): string {
  return canonicalSha256(
    [...fields]
      .sort((left, right) => left.fieldId.localeCompare(right.fieldId))
      .map(({ fieldId, intent }) => ({
        contractVersion: TEMPLATE_TWIN_FIELD_INTENT_CONTRACT_VERSION,
        fieldId,
        intentKind: intent.intentKind,
        decisionId: intent.decisionId,
        version: intent.version,
        supportedConcept: intent.supportedConcept,
        customConceptId: intent.customConceptId,
        customSpecSha256:
          intent.customSpec === null
            ? null
            : computeTemplateFieldSpecificationContentSha256(intent.customSpec),
        reasonSha256: reasonSha256(intent.reason),
      })),
  );
}

export function customConceptSpecifications(
  fields: ReadonlyArray<{ intent: TemplateTwinFieldIntentView }>,
): CertifiedTemplateFieldSpecification[] {
  return fields.flatMap(({ intent }) =>
    intent.intentKind === 'custom_concept' && intent.customSpec
      ? [intent.customSpec]
      : [],
  );
}

/** Applies only a physician-certified scalar custom specification to its
 * deterministically bound ordinary placeholder. The immutable renderer
 * binding/path is unchanged; this effective field shape is used solely by the
 * resolver and independent clinical validator. */
export function fieldsWithCertifiedCustomIntent(input: {
  fields: readonly TemplateField[];
  intents: ReadonlyArray<{ fieldId: string; intent: TemplateTwinFieldIntentView }>;
}): TemplateField[] {
  const intentById = new Map(
    input.intents.map((entry) => [entry.fieldId, entry.intent]),
  );
  return input.fields.map((field) => {
    const intent = intentById.get(field.fieldId);
    const spec = intent?.intentKind === 'custom_concept'
      ? intent.customSpec
      : null;
    if (!spec) return field;
    if (!fieldRequiresExplicitIntent(field) || spec.fieldId !== field.fieldId) {
      throw new Error('A custom field specification does not match its placeholder binding.');
    }
    const kind = spec.dataType === 'boolean' ? 'checkbox' : spec.dataType;
    return {
      ...field,
      kind,
      allowedOptions:
        spec.dataType === 'single_select'
          ? spec.allowedOptions.map((option) => ({
              ordinal: option.ordinal,
              value: option.value,
              displayText: option.displayText,
            }))
          : [],
      required: spec.required,
      clinicallyMaterial: true,
      unknownPolicy: spec.unknownPolicy,
    } as TemplateField;
  });
}
