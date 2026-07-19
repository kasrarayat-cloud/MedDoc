import { createHash } from 'node:crypto';

import { z } from 'zod';

import { canonicalJson, canonicalSha256 } from '../canonical';
import type { TemplateDocIR, TemplateField } from '../ir';
import {
  TEMPLATE_TWIN_SUPPORTED_CONCEPTS,
  TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION,
} from '../supported-concepts';

export const PHYSICIAN_INTENT_MANIFEST_VERSION =
  'template-twin-physician-intent-manifest/1.0.0' as const;
export const PHYSICIAN_INTENT_DECISION_VERSION =
  'template-twin-physician-intent-decision/1.0.0' as const;
export const WM_IOV_PLACEHOLDER_COUNT = 7 as const;

const Sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const CommitShaSchema = z.string().regex(/^[a-f0-9]{40}$/);
const FieldIdSchema = z.string().regex(/^ttf_[a-f0-9]{24}$/);
const ReferenceNumberSchema = z.string().regex(/^P-0[1-7]$/);
const IsoDateTimeSchema = z.string().datetime({ offset: true });

const ExistingConceptSchema = z
  .object({
    concept: z.string().min(1).max(160),
    physicianLabel: z.string().min(1).max(240),
  })
  .strict();

const EmptyDecisionPromptSchema = z
  .object({
    intent: z.null(),
    requiredness: z.null(),
    dataType: z.null(),
    units: z.array(z.never()).length(0),
    allowedValues: z.array(z.never()).length(0),
    polarityAndDenial: z.null(),
    temporality: z.array(z.never()).length(0),
    laterality: z.array(z.never()).length(0),
    blankUnknownPolicy: z.null(),
    maximumLengthOrRange: z.null(),
    positiveSyntheticExample: z.null(),
    negativeSyntheticExample: z.null(),
    ambiguitySyntheticExample: z.null(),
  })
  .strict();

export const PhysicianIntentManifestFieldSchema = z
  .object({
    fieldId: FieldIdSchema,
    referenceNumber: ReferenceNumberSchema,
    documentSection: z.enum(['document_body', 'header', 'footer']),
    location: z
      .object({
        partName: z.string().min(1).max(240),
        tableIndex: z.number().int().nonnegative().nullable(),
        rowIndex: z.number().int().nonnegative().nullable(),
        cellIndex: z.number().int().nonnegative().nullable(),
        paragraphOrdinal: z.number().int().nonnegative(),
        certifiedPathSha256: Sha256Schema,
      })
      .strict(),
    safeVisibleContext: z.string().min(20).max(240),
    sourceTextDisclosure: z.literal('withheld_from_offline_packet'),
    placeholderSyntax: z.enum(['angle', 'square', 'curly', 'underscore']),
    detectedStructuralType: z.literal('ORDINARY_PLACEHOLDER_TOKEN_V1'),
    tokenTextSha256: Sha256Schema,
    certifiedBindingSha256: Sha256Schema,
    bindingOrdinal: z.number().int().nonnegative(),
    sourceControlFingerprintSha256: Sha256Schema,
    availableExistingClinicalConcepts: z.array(ExistingConceptSchema).min(1),
    permittedIntentChoices: z.tuple([
      z.literal('supported_concept'),
      z.literal('custom_scalar_concept'),
      z.literal('intentionally_static'),
      z.literal('unresolved'),
    ]),
    unansweredDecision: EmptyDecisionPromptSchema,
    signingConsequence: z.literal(
      'Unresolved, contradictory, or insufficiently tested clinical intent blocks formal certification and signing.',
    ),
  })
  .strict();

const PhysicianIntentManifestContentSchema = z
  .object({
    contractVersion: z.literal(PHYSICIAN_INTENT_MANIFEST_VERSION),
    sourceCommit: CommitShaSchema,
    sourceDocumentSha256: Sha256Schema,
    compilerVersion: z.string().min(1).max(160),
    irSchemaVersion: z.number().int().positive(),
    generatedAtIso: IsoDateTimeSchema,
    purpose: z.literal('offline_physician_review_worksheet_only'),
    certificationEffect: z.literal('none_authenticated_quillmd_certification_required'),
    safetyNotice: z.literal(
      'Only a licensed physician may define clinical intent. This worksheet cannot activate a template or authorize signing.',
    ),
    conceptRegistryVersion: z.literal(TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION),
    fields: z.array(PhysicianIntentManifestFieldSchema).length(WM_IOV_PLACEHOLDER_COUNT),
  })
  .strict();

export const PhysicianIntentManifestSchema = PhysicianIntentManifestContentSchema.extend({
  manifestSha256: Sha256Schema,
}).strict();
export type PhysicianIntentManifest = z.infer<typeof PhysicianIntentManifestSchema>;

const RequirednessSchema = z.enum(['required', 'optional']);
const UnknownPolicySchema = z.enum(['blank', 'not_documented', 'requires_input']);
const TemporalitySchema = z.enum(['current', 'historical', 'planned', 'unknown']);
const LateralitySchema = z.enum([
  'left',
  'right',
  'bilateral',
  'midline',
  'not_applicable',
  'unknown',
]);

const BaseClinicalPolicyShape = {
  requiredness: RequirednessSchema,
  unknownPolicy: UnknownPolicySchema,
  polarityAndDenial: z
    .object({
      allowExplicitDenial: z.boolean(),
      exactDeniedOutput: z.string().min(1).max(240).nullable(),
    })
    .strict()
    .superRefine((value, context) => {
      if (value.allowExplicitDenial !== (value.exactDeniedOutput !== null)) {
        context.addIssue({
          code: 'custom',
          message: 'An exact denied output is required only when explicit denial is allowed.',
          path: ['exactDeniedOutput'],
        });
      }
    }),
  permittedTemporalities: z.array(TemporalitySchema).min(1).max(4),
  permittedLateralities: z.array(LateralitySchema).min(1).max(6),
  positiveSyntheticExample: z.string().min(10).max(2_000),
  negativeSyntheticExample: z.string().min(10).max(2_000),
  ambiguitySyntheticExample: z.string().min(10).max(2_000),
  signingConsequenceAcknowledged: z.literal(true),
} as const;

const NarrativePolicySchema = z
  .object({
    dataType: z.literal('narrative_text'),
    ...BaseClinicalPolicyShape,
    maximumLength: z.number().int().min(1).max(4_000),
  })
  .strict();
const NumberPolicySchema = z
  .object({
    dataType: z.literal('number'),
    ...BaseClinicalPolicyShape,
    numericRange: z
      .object({
        minimum: z.number().finite().nullable(),
        maximum: z.number().finite().nullable(),
      })
      .strict(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.numericRange.minimum !== null &&
      value.numericRange.maximum !== null &&
      value.numericRange.minimum > value.numericRange.maximum
    ) {
      context.addIssue({ code: 'custom', message: 'Minimum cannot exceed maximum.', path: ['numericRange'] });
    }
  });
const MeasurementPolicySchema = z
  .object({
    dataType: z.literal('measurement'),
    ...BaseClinicalPolicyShape,
    exactUnits: z.array(z.string().trim().min(1).max(40)).min(1).max(16),
    numericRange: z
      .object({
        minimum: z.number().finite().nullable(),
        maximum: z.number().finite().nullable(),
      })
      .strict(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.numericRange.minimum !== null &&
      value.numericRange.maximum !== null &&
      value.numericRange.minimum > value.numericRange.maximum
    ) {
      context.addIssue({ code: 'custom', message: 'Minimum cannot exceed maximum.', path: ['numericRange'] });
    }
  });
const DatePolicySchema = z.object({ dataType: z.literal('date'), ...BaseClinicalPolicyShape }).strict();
const BooleanPolicySchema = z.object({ dataType: z.literal('boolean'), ...BaseClinicalPolicyShape }).strict();
const SingleSelectPolicySchema = z
  .object({
    dataType: z.literal('single_select'),
    ...BaseClinicalPolicyShape,
    exactAllowedValues: z.array(z.string().min(1).max(240)).min(1).max(16),
  })
  .strict();

export const PhysicianClinicalPolicySchema = z.discriminatedUnion('dataType', [
  NarrativePolicySchema,
  NumberPolicySchema,
  MeasurementPolicySchema,
  DatePolicySchema,
  BooleanPolicySchema,
  SingleSelectPolicySchema,
]);

const DecisionIdentityShape = {
  fieldId: FieldIdSchema,
  referenceNumber: ReferenceNumberSchema,
} as const;

export const PhysicianPlaceholderDecisionSchema = z.discriminatedUnion('intent', [
  z
    .object({
      ...DecisionIdentityShape,
      intent: z.literal('supported_concept'),
      supportedConcept: z.string().min(1).max(160),
      clinicalPolicy: PhysicianClinicalPolicySchema,
    })
    .strict(),
  z
    .object({
      ...DecisionIdentityShape,
      intent: z.literal('custom_scalar_concept'),
      physicianFacingName: z.string().min(2).max(160),
      physicianDescription: z.string().min(10).max(1_000),
      evidenceCues: z.array(z.string().trim().min(2).max(120)).min(1).max(12),
      clinicalPolicy: PhysicianClinicalPolicySchema,
    })
    .strict(),
  z
    .object({
      ...DecisionIdentityShape,
      intent: z.literal('intentionally_static'),
      reason: z.string().min(10).max(500),
      signingConsequenceAcknowledged: z.literal(true),
    })
    .strict(),
  z
    .object({
      ...DecisionIdentityShape,
      intent: z.literal('unresolved'),
      reason: z.string().min(10).max(500),
      signingConsequenceAcknowledged: z.literal(true),
    })
    .strict(),
]);
export type PhysicianPlaceholderDecision = z.infer<typeof PhysicianPlaceholderDecisionSchema>;

export const PhysicianIntentDecisionPayloadSchema = z
  .object({
    contractVersion: z.literal(PHYSICIAN_INTENT_DECISION_VERSION),
    sourceCommit: CommitShaSchema,
    sourceDocumentSha256: Sha256Schema,
    manifestSha256: Sha256Schema,
    reviewer: z
      .object({
        name: z.string().min(2).max(160),
        professionalRole: z.literal('licensed_physician'),
        jurisdiction: z.string().min(2).max(160),
        licenseOrRegistrationReference: z.string().min(2).max(160),
      })
      .strict(),
    reviewedAtIso: IsoDateTimeSchema,
    attestation: z
      .object({
        IAmTheLicensedPhysicianNamedAbove: z.literal(true),
        IUsedSyntheticExamplesOnly: z.literal(true),
        IReviewedEveryPlaceholderWithoutDelegatingClinicalJudgment: z.literal(true),
        IUnderstandThisWorksheetDoesNotCertifyOrActivateTheTemplate: z.literal(true),
        IUnderstandFormalAuthenticatedReviewIsStillRequired: z.literal(true),
      })
      .strict(),
    decisions: z.array(PhysicianPlaceholderDecisionSchema).length(WM_IOV_PLACEHOLDER_COUNT),
  })
  .strict();

export const PhysicianIntentDecisionFileSchema = z
  .object({
    payload: PhysicianIntentDecisionPayloadSchema,
    payloadSha256: Sha256Schema,
  })
  .strict();
export type PhysicianIntentDecisionFile = z.infer<typeof PhysicianIntentDecisionFileSchema>;

function documentSection(partName: string): 'document_body' | 'header' | 'footer' {
  if (/^word\/header\d*\.xml$/u.test(partName)) return 'header';
  if (/^word\/footer\d*\.xml$/u.test(partName)) return 'footer';
  return 'document_body';
}

function isOrdinaryPlaceholder(field: TemplateField): boolean {
  return (
    field.rendererBinding.bindingType === 'ordinary_placeholder' &&
    field.rendererBinding.bindingProfile === 'ORDINARY_PLACEHOLDER_TOKEN_V1' &&
    field.rendererBinding.ordinaryPlaceholder?.clinicalMappingStatus === 'needs_confirmation'
  );
}

export function buildWmIovPhysicianIntentManifest(input: {
  ir: TemplateDocIR;
  sourceCommit: string;
  sourceDocumentSha256: string;
  generatedAtIso: string;
}): PhysicianIntentManifest {
  const placeholders = input.ir.fields
    .filter(isOrdinaryPlaceholder)
    .sort((left, right) => left.displayOrder - right.displayOrder || left.fieldId.localeCompare(right.fieldId));
  if (placeholders.length !== WM_IOV_PLACEHOLDER_COUNT) {
    throw new Error(
      `TT_HUMAN_GATE_PLACEHOLDER_COUNT: expected exactly ${WM_IOV_PLACEHOLDER_COUNT} ordinary placeholders, found ${placeholders.length}.`,
    );
  }

  const concepts = TEMPLATE_TWIN_SUPPORTED_CONCEPTS.map(({ concept, physicianLabel }) => ({
    concept,
    physicianLabel,
  })).sort((left, right) => left.physicianLabel.localeCompare(right.physicianLabel));

  const fields = placeholders.map((field, index) => {
    const binding = field.rendererBinding;
    const placeholder = binding.ordinaryPlaceholder!;
    const referenceNumber = `P-0${index + 1}` as `P-0${1 | 2 | 3 | 4 | 5 | 6 | 7}`;
    return PhysicianIntentManifestFieldSchema.parse({
      fieldId: field.fieldId,
      referenceNumber,
      documentSection: documentSection(binding.partName),
      location: {
        partName: binding.partName,
        tableIndex: binding.tableIndex,
        rowIndex: binding.rowIndex,
        cellIndex: binding.cellIndex,
        paragraphOrdinal: binding.ordinal,
        certifiedPathSha256: canonicalSha256({
          partName: binding.partName,
          canonicalPath: binding.canonicalPath,
        }),
      },
      safeVisibleContext: `${referenceNumber}: source-adjacent text is intentionally withheld from this offline packet. Confirm meaning against the authenticated QuillMD preview.`,
      sourceTextDisclosure: 'withheld_from_offline_packet',
      placeholderSyntax: placeholder.tokenSyntax,
      detectedStructuralType: 'ORDINARY_PLACEHOLDER_TOKEN_V1',
      tokenTextSha256: placeholder.tokenTextSha256,
      certifiedBindingSha256: binding.certifiedBindingSha256,
      bindingOrdinal: binding.ordinal,
      sourceControlFingerprintSha256: binding.sourceControlSha256,
      availableExistingClinicalConcepts: concepts,
      permittedIntentChoices: [
        'supported_concept',
        'custom_scalar_concept',
        'intentionally_static',
        'unresolved',
      ],
      unansweredDecision: {
        intent: null,
        requiredness: null,
        dataType: null,
        units: [],
        allowedValues: [],
        polarityAndDenial: null,
        temporality: [],
        laterality: [],
        blankUnknownPolicy: null,
        maximumLengthOrRange: null,
        positiveSyntheticExample: null,
        negativeSyntheticExample: null,
        ambiguitySyntheticExample: null,
      },
      signingConsequence:
        'Unresolved, contradictory, or insufficiently tested clinical intent blocks formal certification and signing.',
    });
  });

  const content = PhysicianIntentManifestContentSchema.parse({
    contractVersion: PHYSICIAN_INTENT_MANIFEST_VERSION,
    sourceCommit: input.sourceCommit,
    sourceDocumentSha256: input.sourceDocumentSha256,
    compilerVersion: input.ir.compilerVersion,
    irSchemaVersion: input.ir.irSchemaVersion,
    generatedAtIso: input.generatedAtIso,
    purpose: 'offline_physician_review_worksheet_only',
    certificationEffect: 'none_authenticated_quillmd_certification_required',
    safetyNotice:
      'Only a licensed physician may define clinical intent. This worksheet cannot activate a template or authorize signing.',
    conceptRegistryVersion: TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION,
    fields,
  });
  return PhysicianIntentManifestSchema.parse({
    ...content,
    manifestSha256: canonicalSha256(content),
  });
}

function uniqueStrings(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export interface PhysicianIntentDecisionValidation {
  readonly status: 'PASS' | 'BLOCKED';
  readonly blockerCodes: readonly string[];
  readonly decisionFile: PhysicianIntentDecisionFile;
}

export function validatePhysicianIntentDecisionFile(input: {
  manifest: PhysicianIntentManifest;
  decisionFile: unknown;
}): PhysicianIntentDecisionValidation {
  const manifest = PhysicianIntentManifestSchema.parse(input.manifest);
  const decisionFile = PhysicianIntentDecisionFileSchema.parse(input.decisionFile);
  if (canonicalSha256(decisionFile.payload) !== decisionFile.payloadSha256) {
    throw new Error('TT_HUMAN_GATE_DECISION_HASH_MISMATCH: physician decision payload was altered.');
  }
  const manifestContent: Record<string, unknown> = { ...manifest };
  delete manifestContent.manifestSha256;
  const expectedManifestHash = canonicalSha256(
    PhysicianIntentManifestContentSchema.parse(manifestContent),
  );
  if (manifest.manifestSha256 !== expectedManifestHash) {
    throw new Error('TT_HUMAN_GATE_MANIFEST_HASH_MISMATCH: physician manifest was altered.');
  }
  if (
    decisionFile.payload.sourceCommit !== manifest.sourceCommit ||
    decisionFile.payload.sourceDocumentSha256 !== manifest.sourceDocumentSha256 ||
    decisionFile.payload.manifestSha256 !== manifest.manifestSha256
  ) {
    throw new Error('TT_HUMAN_GATE_SOURCE_MISMATCH: decision does not match this manifest and commit.');
  }
  const expectedByFieldId = new Map(manifest.fields.map((field) => [field.fieldId, field]));
  if (!uniqueStrings(decisionFile.payload.decisions.map((decision) => decision.fieldId))) {
    throw new Error('TT_HUMAN_GATE_DUPLICATE_DECISION: every placeholder must appear exactly once.');
  }
  for (const decision of decisionFile.payload.decisions) {
    const field = expectedByFieldId.get(decision.fieldId);
    if (!field || field.referenceNumber !== decision.referenceNumber) {
      throw new Error('TT_HUMAN_GATE_FIELD_MISMATCH: decision field/reference does not match the manifest.');
    }
    if (
      decision.intent === 'supported_concept' &&
      !field.availableExistingClinicalConcepts.some(
        (candidate) => candidate.concept === decision.supportedConcept,
      )
    ) {
      throw new Error('TT_HUMAN_GATE_UNSUPPORTED_CONCEPT: choose an exact concept listed in the manifest.');
    }
  }
  const blockerCodes = decisionFile.payload.decisions.some(
    (decision) => decision.intent === 'unresolved',
  )
    ? ['TT_HUMAN_GATE_UNRESOLVED']
    : [];
  return {
    status: blockerCodes.length === 0 ? 'PASS' : 'BLOCKED',
    blockerCodes,
    decisionFile,
  };
}

export function createPhysicianIntentDecisionFile(
  payload: z.input<typeof PhysicianIntentDecisionPayloadSchema>,
): PhysicianIntentDecisionFile {
  const parsed = PhysicianIntentDecisionPayloadSchema.parse(payload);
  return {
    payload: parsed,
    payloadSha256: createHash('sha256').update(canonicalJson(parsed), 'utf8').digest('hex'),
  };
}
