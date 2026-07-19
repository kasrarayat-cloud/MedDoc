import { SemanticMappingSchema, type SemanticMapping } from "./ir";
import type { TemplateTwinWorkspace } from "./client-types";
import {
  TemplateTwinFieldIntentInputSchema,
  type TemplateTwinFieldIntentInput,
} from "./field-intent";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "./staging-qa-fixture-contract";
import {
  TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT,
  TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION,
  TEMPLATE_TWIN_STAGING_QA_REVIEWED_STRUCTURE_CONTRACT,
  type TemplateTwinStagingQaPhysicianReviewSummary,
  type TemplateTwinStagingQaReviewedMappingDraft,
} from "./staging-qa-reviewed-mapping-contract";
import { isSupportedTemplateTwinConcept } from "./supported-concepts";
import { readTemplateTwinWorkspace } from "./workspace-read";

const SHA256 = /^[a-f0-9]{64}$/u;
const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export class TemplateTwinStagingQaReviewedMappingsError extends Error {
  readonly code:
    | "UNAVAILABLE"
    | "NOT_EDITABLE"
    | "CONTRACT_MISMATCH";

  constructor(
    code: TemplateTwinStagingQaReviewedMappingsError["code"],
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinStagingQaReviewedMappingsError";
    this.code = code;
  }
}

function unavailable(message: string): never {
  throw new TemplateTwinStagingQaReviewedMappingsError(
    "CONTRACT_MISMATCH",
    message,
  );
}

function assertReviewedStructure(workspace: TemplateTwinWorkspace): void {
  for (const [setting, expected] of Object.entries(
    TEMPLATE_TWIN_STAGING_QA_REVIEWED_STRUCTURE_CONTRACT,
  )) {
    const actual = workspace.stats[
      setting as keyof typeof TEMPLATE_TWIN_STAGING_QA_REVIEWED_STRUCTURE_CONTRACT
    ];
    if (actual !== expected) {
      unavailable(
        `Synthetic fixture structure setting ${setting} is ${String(actual)}; expected ${expected}.`,
      );
    }
  }
  if (
    workspace.fields.length !==
      TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT.length ||
    workspace.unsupported.length !== 0
  ) {
    unavailable("Synthetic fixture field inventory does not match the reviewed contract.");
  }

  const fieldById = new Map(
    workspace.fields.map((item) => [item.field.fieldId, item]),
  );
  if (fieldById.size !== workspace.fields.length) {
    unavailable("Synthetic fixture field inventory contains a duplicate field ID.");
  }

  for (const reviewed of TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT) {
    const item = fieldById.get(reviewed.fieldId);
    if (!item) {
      unavailable(`Synthetic fixture field ${reviewed.fieldLabel} is missing.`);
    }
    const field = item.field;
    const checks: ReadonlyArray<readonly [string, unknown, unknown]> = [
      ["field label", field.originalLabel, reviewed.fieldLabel],
      ["display order", field.displayOrder, reviewed.displayOrder],
      ["field kind", field.kind, reviewed.fieldKind],
      ["binding type", field.rendererBinding.bindingType, reviewed.bindingType],
      [
        "source binding identity",
        field.rendererBinding.sourceBindingIdentitySha256,
        reviewed.sourceBindingIdentitySha256,
      ],
    ];
    const mismatch = checks.find(([, actual, expected]) => actual !== expected);
    if (mismatch) {
      unavailable(
        `Synthetic fixture field ${reviewed.fieldLabel} has an unexpected ${mismatch[0]}.`,
      );
    }
    if (item.mapping.fieldId !== reviewed.fieldId) {
      unavailable(
        `Synthetic fixture field ${reviewed.fieldLabel} is bound to a different mapping row.`,
      );
    }
  }
}

function reviewedMapping(
  field: (typeof TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT)[number],
): SemanticMapping {
  if (!isSupportedTemplateTwinConcept(field.clinicalConcept)) {
    unavailable(
      `Synthetic fixture field ${field.fieldLabel} names an unsupported reviewed clinical detail.`,
    );
  }
  return SemanticMappingSchema.parse({
    fieldId: field.fieldId,
    clinicalConcept: field.clinicalConcept,
    expectedDataType: field.expectedDataType,
    polarityBehavior: field.polarityBehavior,
    temporality: "any",
    laterality: "not_applicable",
    unitPolicy: "not_applicable",
    approvedSynonyms: [],
    required: true,
    blankPolicy: "blank",
    unknownPolicy: "requires_input",
    practiceDefault: null,
    status: "certified",
  });
}

function physicianReviewSummary(): TemplateTwinStagingQaPhysicianReviewSummary {
  return {
    title: "Physician review of the synthetic mapping set",
    fixtureLabel: "Template Twin Synthetic QA Fixture",
    fieldCount: 8,
    fields: TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT.map((field) => ({
      fieldId: field.fieldId,
      fieldLabel: field.fieldLabel,
      clinicalConcept: field.clinicalConcept,
      clinicalDetailLabel: field.physicianDetailLabel,
      settings: {
        expectedDataType: field.expectedDataType,
        polarityBehavior: field.polarityBehavior,
        temporality: "any",
        laterality: "not_applicable",
        unitPolicy: "not_applicable",
        whenNotStated: "requires_input",
        requiredBeforeSigning: true,
      },
    })),
    settings: {
      approvedSynonyms: "none",
      practiceDefaults: "none",
      blankPolicy: "blank",
      missingClinicalDetail: "requires_input",
      requiredBeforeSigning: true,
    },
    explicitConfirmationRequired: true,
    activationPerformed: false,
  };
}

/**
 * Build a client draft from the reviewed fixture contract. This function is
 * intentionally pure: loading reviewed values never persists a mapping,
 * records a field intent, runs a provider, certifies, or activates a version.
 */
export function buildTemplateTwinStagingQaReviewedMappingDraft(
  workspace: TemplateTwinWorkspace,
): TemplateTwinStagingQaReviewedMappingDraft {
  if (
    !workspace.stagingQaFixtureSource ||
    workspace.source.sha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    workspace.source.sizeBytes !==
      TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES ||
    workspace.source.mimeType !== DOCX_MIME
  ) {
    throw new TemplateTwinStagingQaReviewedMappingsError(
      "UNAVAILABLE",
      "Reviewed synthetic mappings are available only for the exact allowlisted fixture.",
    );
  }
  if (
    !workspace.canEdit ||
    workspace.template.status !== "draft" ||
    workspace.template.certificationStatus === "certified"
  ) {
    throw new TemplateTwinStagingQaReviewedMappingsError(
      "NOT_EDITABLE",
      "Reviewed synthetic mappings can be loaded only into an editable draft version.",
    );
  }
  if (
    !SHA256.test(workspace.mappingsSha256) ||
    !SHA256.test(workspace.fieldIntentsSha256)
  ) {
    unavailable("Synthetic fixture optimistic state is invalid.");
  }
  assertReviewedStructure(workspace);

  const mappings = TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT.map(
    reviewedMapping,
  );
  const fieldIntents: TemplateTwinFieldIntentInput[] =
    TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT.flatMap((field) =>
      field.bindingType === "ordinary_placeholder"
        ? [
            TemplateTwinFieldIntentInputSchema.parse({
              fieldId: field.fieldId,
              intentKind: "supported_concept" as const,
              supportedConcept: field.clinicalConcept,
            }),
          ]
        : [],
    );
  if (mappings.length !== 8 || fieldIntents.length !== 1) {
    unavailable("Synthetic fixture reviewed mapping decisions are incomplete.");
  }

  return {
    contractVersion:
      TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION,
    fixture: {
      sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
      sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    },
    template: {
      id: workspace.template.id,
      version: workspace.template.version,
    },
    expectedMappingsSha256: workspace.mappingsSha256,
    expectedFieldIntentsSha256: workspace.fieldIntentsSha256,
    mappings,
    fieldIntents,
    physicianReviewSummary: physicianReviewSummary(),
  };
}

interface ReviewedMappingDependencies {
  readonly readWorkspace: typeof readTemplateTwinWorkspace;
}

/** Doctor- and practice-scoped read wrapper used by the authenticated route. */
export async function loadTemplateTwinStagingQaReviewedMappingDraft(input: {
  readonly noteTemplateId: string;
  readonly doctorId: string;
  readonly practiceId: string;
  readonly dependencies?: Partial<ReviewedMappingDependencies>;
}): Promise<TemplateTwinStagingQaReviewedMappingDraft> {
  const readWorkspace =
    input.dependencies?.readWorkspace ?? readTemplateTwinWorkspace;
  const workspace = await readWorkspace({
    noteTemplateId: input.noteTemplateId,
    doctorId: input.doctorId,
    practiceId: input.practiceId,
  });
  if (!workspace || workspace.template.id !== input.noteTemplateId) {
    throw new TemplateTwinStagingQaReviewedMappingsError(
      "UNAVAILABLE",
      "Reviewed synthetic mappings are unavailable.",
    );
  }
  return buildTemplateTwinStagingQaReviewedMappingDraft(workspace);
}
