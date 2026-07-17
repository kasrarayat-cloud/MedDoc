import prisma from "@meddoc/db";

import { SemanticMappingSchema, TemplateDocIRSchema } from "./ir";
import { templateTwinMappingsSha256 } from "./mapping-hash";
import {
  fieldRequiresExplicitIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  type PersistedTemplateTwinFieldIntent,
} from "./field-intent";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "./staging-qa-fixtures";

const SHA256 = /^[a-f0-9]{64}$/u;

export interface TemplateTwinStagingQaExpectedMappingConfirmation {
  readonly mappingsSha256?: string;
  readonly fieldIntentsSha256?: string;
}

interface DurableMappingField {
  id: string;
  fieldId: string;
  mapping: {
    clinicalConcept: string | null;
    expectedDataType: string;
    polarityBehavior: string;
    temporality: string | null;
    laterality: string | null;
    unitPolicy: string | null;
    approvedSynonyms: unknown;
    required: boolean;
    blankPolicy: string;
    unknownPolicy: string;
    practiceDefault: string | null;
    mappingStatus: string;
  } | null;
  intentDecisions: Array<{
    id: string;
    version: number;
    intentKind: string;
    supportedConcept: string | null;
    customConceptId: string | null;
    customSpec: unknown;
    customSpecSha256: string | null;
    reason: string | null;
    decidedById: string;
    decidedAt: Date;
  }>;
}

/**
 * Rebuild the physician-confirmed mapping proof from durable rows. This runs
 * before any process/resource/rollout provider admission for the exact
 * staging artifact, so a voice/privacy/model callback cannot be reached with
 * incomplete or stale mappings.
 */
export async function confirmTemplateTwinStagingQaMappings(input: {
  noteTemplateId: string;
  doctorId: string;
  practiceId: string;
  source: { sha256: string; sizeBytes: number };
  expected?: TemplateTwinStagingQaExpectedMappingConfirmation;
}): Promise<boolean> {
  if (
    input.source.sha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    input.source.sizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES ||
    (input.expected?.mappingsSha256 !== undefined &&
      !SHA256.test(input.expected.mappingsSha256)) ||
    (input.expected?.fieldIntentsSha256 !== undefined &&
      !SHA256.test(input.expected.fieldIntentsSha256))
  ) {
    return false;
  }

  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.doctorId,
      templateKind: "template_twin_docx",
      templateTwinCompiledVersion: {
        is: {
          sourceArtifact: {
            is: {
              practiceId: input.practiceId,
              validationStatus: "accepted",
              sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
              sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
            },
          },
        },
      },
    },
    select: {
      templateTwinCompiledVersion: {
        select: {
          compiledDocumentIr: true,
          fields: {
            orderBy: { displayOrder: "asc" },
            select: {
              id: true,
              fieldId: true,
              mapping: {
                select: {
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
                  unknownPolicy: true,
                  practiceDefault: true,
                  mappingStatus: true,
                },
              },
              intentDecisions: {
                orderBy: { version: "desc" },
                take: 1,
                select: {
                  id: true,
                  version: true,
                  intentKind: true,
                  supportedConcept: true,
                  customConceptId: true,
                  customSpec: true,
                  customSpecSha256: true,
                  reason: true,
                  decidedById: true,
                  decidedAt: true,
                },
              },
            },
          },
        },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion as
    | { compiledDocumentIr: unknown; fields: DurableMappingField[] }
    | null
    | undefined;
  if (!compiled) return false;

  try {
    const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
    if (compiled.fields.length !== ir.fields.length) return false;
    const persistedByFieldId = new Map(
      compiled.fields.map((field) => [field.fieldId, field]),
    );
    const mappings = ir.fields.map((field) => {
      const persisted = persistedByFieldId.get(field.fieldId);
      const mapping = persisted?.mapping;
      if (!mapping || mapping.mappingStatus.toLowerCase() !== "certified") {
        throw new Error("mapping not confirmed");
      }
      return SemanticMappingSchema.parse({
        fieldId: field.fieldId,
        clinicalConcept: mapping.clinicalConcept,
        expectedDataType: mapping.expectedDataType,
        polarityBehavior: mapping.polarityBehavior,
        temporality: mapping.temporality,
        laterality: mapping.laterality,
        unitPolicy: mapping.unitPolicy,
        approvedSynonyms: Array.isArray(mapping.approvedSynonyms)
          ? mapping.approvedSynonyms
          : [],
        required: mapping.required,
        blankPolicy: mapping.blankPolicy,
        unknownPolicy: mapping.unknownPolicy,
        practiceDefault: mapping.practiceDefault,
        status: "certified",
      });
    });
    const mappingsSha256 = templateTwinMappingsSha256(mappings);
    if (
      input.expected?.mappingsSha256 !== undefined &&
      input.expected.mappingsSha256 !== mappingsSha256
    ) {
      return false;
    }

    const intents = ir.fields
      .filter(fieldRequiresExplicitIntent)
      .map((field) => {
        const persisted = persistedByFieldId.get(field.fieldId);
        const decision = persisted?.intentDecisions[0];
        if (!persisted || !decision || decision.intentKind === "unresolved") {
          throw new Error("field intent not confirmed");
        }
        return {
          fieldId: field.fieldId,
          intent: parsePersistedFieldIntent({
            ...decision,
            fieldDefinitionId: persisted.id,
            fieldId: field.fieldId,
          } satisfies PersistedTemplateTwinFieldIntent),
        };
      });
    const fieldIntentsSha256 = templateTwinFieldIntentsSha256(intents);
    return (
      input.expected?.fieldIntentsSha256 === undefined ||
      input.expected.fieldIntentsSha256 === fieldIntentsSha256
    );
  } catch {
    return false;
  }
}
