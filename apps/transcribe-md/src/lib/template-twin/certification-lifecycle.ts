import { randomUUID } from "node:crypto";

import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";
import type { ModelClient } from "@meddoc/ai";

import {
  SemanticMappingSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from "./ir";
import { isMappingTypeCompatible } from "./semantic-mapping";
import { templateTwinMappingsSha256 } from "./mapping-hash";
import { readTemplateTwinWorkspace } from "./workspace-read";
import type { TemplateTwinWorkspace } from "./client-types";
import { parseTemplateTwinArtifactKey } from "./storage";
import { canonicalSha256 } from "./canonical";
import { validateTemplateTwin } from "./validation";
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON,
  isSupportedTemplateTwinConcept,
} from "./supported-concepts";
import type { TemplateTwinConceptProvider } from "./supported-concepts";
import { evaluateTemplateTwinCertificationCoverage } from "./certification-coverage";
import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { templateTwinSyntheticTestProvenanceSha256 } from "./synthetic-test-provenance";
import {
  assertTemplateTwinSourceProvenance,
  templateTwinSyntheticProofSourceEvidenceSha256,
  TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
} from "./source-phi-evidence";
import { lockAndAssertTemplateTwinStaticAssetBindingsCurrent } from "./static-assets";
import {
  TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
  TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
  nativeIdentityFromRendererBinding,
  rendererBindingFingerprintSha256,
} from "../note-template-docx/binding-fingerprint";
import {
  certifyCustomFieldSpecification,
  customConceptSpecifications,
  fieldRequiresExplicitIntent,
  fieldsWithCertifiedCustomIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
  type TemplateTwinFieldIntentInput,
  type TemplateTwinFieldIntentView,
  TemplateTwinFieldIntentInputSchema,
} from "./field-intent";
import {
  assertTemplateFieldSpecificationSetWithinLimits,
  computeTemplateFieldSpecificationContentSha256,
  createCertifiedCustomConceptProvider,
  templateFieldSpecificationAuthoredText,
} from "./custom-concepts";
import type { CertifiedTemplateFieldSpecification } from "./custom-concepts/specification";
import {
  assertTemplateTwinCustomExamplesReadyForCertification,
  TemplateTwinCustomExampleError,
} from "./custom-example-service";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  assertTemplateTwinAuthoredCorpusPhiFree,
  TemplateTwinSyntheticEvidenceRejectedError,
} from "./synthetic-evidence-gate";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON,
} from "./staging-qa-fixtures";
import {
  templateTwinMappingFieldError,
  validateTemplateTwinClinicalDetail,
  type TemplateTwinMappingFieldError,
  type TemplateTwinMappingSetting,
} from "./mapping-validation";

export class TemplateTwinLifecycleError extends Error {
  readonly code:
    | "NOT_FOUND"
    | "IMMUTABLE"
    | "CONFLICT"
    | "FIELD_SET_MISMATCH"
    | "MAPPING_INVALID"
    | "UNSUPPORTED_CLINICAL_CONCEPT"
    | "CERTIFICATION_BLOCKED"
    | "ROLLOUT_CHANGED";

  constructor(
    code: TemplateTwinLifecycleError["code"],
    message: string,
    readonly fieldErrors: readonly TemplateTwinMappingFieldError[] = [],
  ) {
    super(message);
    this.name = "TemplateTwinLifecycleError";
    this.code = code;
  }
}

function invalidField(
  field: TemplateField,
  setting: TemplateTwinMappingSetting,
  message: string,
): TemplateTwinLifecycleError {
  const issue = templateTwinMappingFieldError({ field, setting, message });
  return new TemplateTwinLifecycleError(
    "MAPPING_INVALID",
    `Field ${issue.fieldNumber} (${issue.fieldLabel}) — ${issue.message}`,
    [issue],
  );
}

export interface TemplateTwinActor {
  userId: string;
  userEmail: string;
  practiceId: string;
  /** Exact rollout generations pinned by fresh physician authorization. */
  rolloutToken: TemplateTwinRolloutToken;
}

async function assertConfigurationRolloutFinality(
  tx: Prisma.TransactionClient,
  actor: TemplateTwinActor,
  operation: string,
): Promise<void> {
  const decision = await lockTemplateTwinRolloutForFinalClaim({
    tx,
    practiceId: actor.practiceId,
    pinnedToken: actor.rolloutToken,
  });
  if (!decision.allowed) {
    throw new TemplateTwinLifecycleError(
      "ROLLOUT_CHANGED",
      `${decision.code}: Template Twin availability changed while ${operation}. Reload and try again.`,
    );
  }
}

interface PersistedMappingRow {
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
}

function fromPersistedMapping(
  fieldId: string,
  row: PersistedMappingRow,
): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms)
      ? row.approvedSynonyms
      : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function dbStatus(
  status: SemanticMapping["status"],
): "RECOGNIZED" | "NEEDS_CONFIRMATION" | "UNSUPPORTED" | "CERTIFIED" {
  switch (status) {
    case "recognized":
      return "RECOGNIZED";
    case "needs_confirmation":
      return "NEEDS_CONFIRMATION";
    case "unsupported":
      return "UNSUPPORTED";
    case "certified":
      return "CERTIFIED";
  }
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

function validPracticeDefault(
  field: TemplateField,
  mapping: SemanticMapping,
): boolean {
  const raw = mapping.practiceDefault;
  if (raw === null) return true;
  if (mapping.status !== "certified") return false;
  switch (field.kind) {
    case "narrative_text":
      return raw.trim().length > 0;
    case "single_select":
      return field.allowedOptions.some(
        (option) => option.value === raw || option.displayText === raw,
      );
    case "multi_select":
      return false;
    case "checkbox":
      return raw === "true" || raw === "false";
    case "date": {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return false;
      const date = new Date(`${raw}T00:00:00Z`);
      return (
        !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === raw
      );
    }
    case "number":
      return /^[-+]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(raw.trim());
    case "measurement":
      return /^[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s+\S+)?$/.test(raw.trim());
  }
}

function mappingMatchesCustomSpecification(
  mapping: SemanticMapping,
  specification: CertifiedTemplateFieldSpecification,
): boolean {
  const expectedDataType =
    specification.dataType === "narrative_text"
      ? "text"
      : specification.dataType;
  const expectedPolarity = specification.polarityPolicy.allowExplicitDenial
    ? "explicit_denial_allowed"
    : specification.dataType === "boolean"
      ? "affirmative_only"
      : "value_only";
  const expectedUnitPolicy =
    specification.dataType === "measurement"
      ? "required"
      : specification.dataType === "number"
        ? "forbidden"
        : "not_applicable";
  return (
    mapping.clinicalConcept === specification.conceptId &&
    mapping.expectedDataType === expectedDataType &&
    mapping.polarityBehavior === expectedPolarity &&
    mapping.temporality === "any" &&
    mapping.laterality === "optional" &&
    mapping.unitPolicy === expectedUnitPolicy &&
    mapping.approvedSynonyms.length === 0 &&
    mapping.required === specification.required &&
    mapping.blankPolicy === specification.unknownPolicy &&
    mapping.unknownPolicy === specification.unknownPolicy &&
    mapping.practiceDefault === null
  );
}

async function loadOwnedCompilation(
  client: Prisma.TransactionClient,
  noteTemplateId: string,
  actor: TemplateTwinActor,
) {
  const row = await client.noteTemplate.findFirst({
    where: {
      id: noteTemplateId,
      doctorId: actor.userId,
      templateKind: "template_twin_docx",
    },
    select: {
      id: true,
      doctorId: true,
      lineageId: true,
      encounterType: true,
      version: true,
      status: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          blockingUnsupportedCount: true,
          latestSyntheticTestManifest: true,
          latestTestMappingsSha256: true,
          latestTestFieldIntentsSha256: true,
          latestTestOutputObjectKey: true,
          latestTestOutputVersionId: true,
          latestTestOutputEtag: true,
          latestTestOutputSha256: true,
          latestTestStaticContentSha256: true,
          latestTestRoundTrip: true,
          latestTestVerifiedAt: true,
          certification: {
            select: { id: true, approvedFieldIntentsSha256: true },
          },
          sourceArtifact: {
            select: {
              practiceId: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              validationStatus: true,
              privacyScanEvidence: true,
            },
          },
          fields: {
            orderBy: { displayOrder: "asc" },
            select: {
              id: true,
              fieldId: true,
              detectionStatus: true,
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
              mapping: {
                select: {
                  id: true,
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
            },
          },
        },
      },
    },
  });
  if (
    !row?.templateTwinCompiledVersion ||
    row.templateTwinCompiledVersion.sourceArtifact.practiceId !==
      actor.practiceId
  ) {
    throw new TemplateTwinLifecycleError(
      "NOT_FOUND",
      "This Template Twin version is stale or unavailable. Refresh the certification workspace.",
    );
  }
  return { template: row, compiled: row.templateTwinCompiledVersion };
}

function currentMappings(
  compiled: Awaited<ReturnType<typeof loadOwnedCompilation>>["compiled"],
) {
  return compiled.fields.map((field) => {
    if (!field.mapping) {
      throw new TemplateTwinLifecycleError(
        "FIELD_SET_MISMATCH",
        "A compiled field has no semantic mapping.",
      );
    }
    return fromPersistedMapping(field.fieldId, field.mapping);
  });
}

type LoadedCompilation = Awaited<
  ReturnType<typeof loadOwnedCompilation>
>["compiled"];

function currentExplicitFieldIntents(
  ir: TemplateDocIR,
  compiled: LoadedCompilation,
): Array<{
  fieldId: string;
  definitionId: string;
  intent: TemplateTwinFieldIntentView;
}> {
  const persisted = new Map(
    compiled.fields.map((field) => [field.fieldId, field]),
  );
  return ir.fields.filter(fieldRequiresExplicitIntent).map((field) => {
    const row = persisted.get(field.fieldId);
    if (!row) {
      throw new TemplateTwinLifecycleError(
        "FIELD_SET_MISMATCH",
        "A placeholder field has no persisted field definition.",
      );
    }
    const decision = row.intentDecisions[0];
    return {
      fieldId: field.fieldId,
      definitionId: row.id,
      intent: decision
        ? parsePersistedFieldIntent({
            ...decision,
            fieldDefinitionId: row.id,
            fieldId: field.fieldId,
          } satisfies PersistedTemplateTwinFieldIntent)
        : unresolvedFieldIntent(),
    };
  });
}

function explicitFieldIntentsSha256(
  intents: ReadonlyArray<{
    fieldId: string;
    intent: TemplateTwinFieldIntentView;
  }>,
): string {
  return templateTwinFieldIntentsSha256(
    intents.map(({ fieldId, intent }) => ({ fieldId, intent })),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function canonicalValuesEqual(left: unknown, right: unknown): boolean {
  try {
    return canonicalSha256(left) === canonicalSha256(right);
  } catch {
    return false;
  }
}

/** Certification must bind the synthetic proof to this exact immutable
 * source, compiled static region, and persisted output. A truthy `verified`
 * bit alone is not an integrity boundary. */
function isVerifiedSyntheticProof(input: {
  roundTrip: unknown;
  sourceSha256: string;
  outputSha256: string;
  staticContentSha256: string;
  expectedStaticContentSha256: string;
  expectedFields: ReadonlyArray<{
    fieldId: string;
    partName: string;
    bindingPath: string;
    canonicalBindingPath: string;
    bindingType: TemplateField["rendererBinding"]["bindingType"];
    bindingProfile?: TemplateField["rendererBinding"]["bindingProfile"];
    bindingOrdinal: number;
    nativeIdentity: ReturnType<typeof nativeIdentityFromRendererBinding>;
    sourceBindingIdentitySha256: string;
    certifiedBindingSha256: string;
    tableLocation: {
      tableIndex: number | null;
      rowIndex: number | null;
      cellIndex: number | null;
    };
    valueSha256: string;
    occurrences: number;
  }>;
}): boolean {
  if (!isRecord(input.roundTrip)) return false;
  const proof = input.roundTrip;
  const proofFields = Array.isArray(proof.fields) ? proof.fields : [];
  const fieldProofById = new Map<string, Record<string, unknown>>();
  for (const candidate of proofFields) {
    if (!isRecord(candidate) || typeof candidate.fieldId !== "string") {
      return false;
    }
    if (fieldProofById.has(candidate.fieldId)) return false;
    fieldProofById.set(candidate.fieldId, candidate);
  }
  const fieldsVerified =
    fieldProofById.size === input.expectedFields.length &&
    input.expectedFields.every((expected) => {
      const field = fieldProofById.get(expected.fieldId);
      const bindingEvidence = field?.bindingEvidence;
      return Boolean(
        field &&
        isRecord(bindingEvidence) &&
        field.status === "verified" &&
        field.partName === expected.partName &&
        field.bindingPath === expected.bindingPath &&
        field.valueSha256 === expected.valueSha256 &&
        Number.isSafeInteger(expected.occurrences) &&
        expected.occurrences > 0 &&
        field.occurrences === expected.occurrences &&
        bindingEvidence.contractVersion ===
          TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION &&
        bindingEvidence.status === "verified" &&
        bindingEvidence.certifiedFingerprintSha256 ===
          expected.certifiedBindingSha256 &&
        bindingEvidence.outputFingerprintSha256 ===
          expected.certifiedBindingSha256 &&
        bindingEvidence.outputPartName === expected.partName &&
        bindingEvidence.outputCanonicalPath === expected.canonicalBindingPath &&
        bindingEvidence.outputBindingType === expected.bindingType &&
        (expected.bindingProfile === undefined
          ? bindingEvidence.outputBindingProfile === undefined
          : bindingEvidence.outputBindingProfile === expected.bindingProfile) &&
        bindingEvidence.outputBindingOrdinal === expected.bindingOrdinal &&
        canonicalValuesEqual(
          bindingEvidence.outputNativeIdentity,
          expected.nativeIdentity,
        ) &&
        bindingEvidence.outputBindingIdentitySha256 ===
          expected.sourceBindingIdentitySha256 &&
        canonicalValuesEqual(
          bindingEvidence.outputTableLocation,
          expected.tableLocation,
        ),
      );
    });
  return (
    input.staticContentSha256 === input.expectedStaticContentSha256 &&
    proof.verificationContractVersion ===
      TEMPLATE_TWIN_READBACK_CONTRACT_VERSION &&
    proof.verified === true &&
    proof.packageCheck === "verified" &&
    proof.fieldCheck === "verified" &&
    proof.staticRegionCheck === "verified" &&
    proof.sourceSha256 === input.sourceSha256 &&
    proof.outputSha256 === input.outputSha256 &&
    Number.isSafeInteger(proof.untouchedEntriesVerified) &&
    Number(proof.untouchedEntriesVerified) >= 0 &&
    Number.isSafeInteger(proof.modifiedPartsVerified) &&
    Number(proof.modifiedPartsVerified) >= 0 &&
    fieldsVerified &&
    Array.isArray(proof.warningCodes) &&
    proof.warningCodes.every((code) => typeof code === "string")
  );
}

function isVerifiedSyntheticManifest(input: {
  manifest: unknown;
  outputObjectKey: string;
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  ir: TemplateDocIR;
  effectiveFields: readonly TemplateField[];
  mappings: readonly SemanticMapping[];
  staticFieldIds: readonly string[];
  conceptProviders: readonly TemplateTwinConceptProvider[];
  fieldIntentsSha256: string;
  customSpecifications: ReturnType<typeof customConceptSpecifications>;
}): boolean {
  const parsed = TemplateTwinFillManifestSchema.safeParse(input.manifest);
  if (!parsed.success) return false;
  const manifest = parsed.data;
  const keyParts = input.outputObjectKey.split("/");
  if (
    keyParts.length !== 8 ||
    keyParts[5] !== canonicalSha256(manifest) ||
    manifest.compiledVersionId !== input.compiledVersionId ||
    manifest.noteTemplateId !== input.noteTemplateId ||
    manifest.noteTemplateVersion !== input.noteTemplateVersion ||
    manifest.compilerVersion !== input.ir.compilerVersion ||
    manifest.resolverVersion !== TEMPLATE_TWIN_RESOLVER_VERSION ||
    manifest.rendererVersion !== TEMPLATE_TWIN_RENDERER_VERSION ||
    manifest.fieldIntentsSha256 !== input.fieldIntentsSha256
  ) {
    return false;
  }
  const expectedFieldIds = input.ir.fields.map((field) => field.fieldId).sort();
  const manifestFieldIds = manifest.fields.map((field) => field.fieldId).sort();
  if (
    new Set(manifestFieldIds).size !== expectedFieldIds.length ||
    canonicalSha256(manifestFieldIds) !== canonicalSha256(expectedFieldIds) ||
    canonicalSha256(manifest.counts) !==
      canonicalSha256(
        templateTwinCounts(manifest.fields, input.effectiveFields),
      )
  ) {
    return false;
  }
  const reproduced = validateTemplateTwin({
    fields: input.effectiveFields,
    mappings: input.mappings,
    facts: manifest.facts,
    resolutions: manifest.fields,
    tables: input.ir.tables,
    unsupported: input.ir.unsupported,
    allowUncertifiedForSyntheticTest: true,
    staticFieldIds: input.staticFieldIds,
    conceptProviders: input.conceptProviders,
    customSpecifications: input.customSpecifications,
    now: manifest.validation.checkedAt,
  });
  return (
    reproduced.valid &&
    reproduced.issues.every((issue) => issue.severity !== "blocking") &&
    canonicalSha256(reproduced) === canonicalSha256(manifest.validation)
  );
}

async function refreshedWorkspace(
  noteTemplateId: string,
  actor: TemplateTwinActor,
): Promise<TemplateTwinWorkspace> {
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: actor.userId,
    practiceId: actor.practiceId,
  });
  if (!workspace) {
    throw new TemplateTwinLifecycleError(
      "NOT_FOUND",
      "This Template Twin version is stale or unavailable. Refresh the certification workspace.",
    );
  }
  return workspace;
}

export async function updateTemplateTwinMappings(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  /** Older generic-template service callers have no explicit placeholder
   * intent set. HTTP callers always send this hash; omission is accepted only
   * when the compiled IR has zero intent-bearing fields. */
  expectedFieldIntentsSha256?: string;
  mappings: readonly SemanticMapping[];
  fieldIntents?: readonly TemplateTwinFieldIntentInput[];
  privacyClient?: Pick<ModelClient, "complete">;
}): Promise<TemplateTwinWorkspace> {
  // Authenticate ownership, mutability, optimistic hashes, and exact compiler
  // field sets before any privacy-provider work. This cheap read is repeated
  // under the final rollout-locked write transaction, closing its TOCTOU gap.
  const preflight = await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      await assertConfigurationRolloutFinality(
        tx,
        input.actor,
        "the mapping and field intent were being checked",
      );
      return loadOwnedCompilation(tx, input.noteTemplateId, input.actor);
    },
    { isolationLevel: "Serializable" },
  );
  if (
    preflight.compiled.certification ||
    preflight.compiled.certificationStatus === "CERTIFIED"
  ) {
    throw new TemplateTwinLifecycleError(
      "IMMUTABLE",
      "Certified Template Twin versions cannot be edited.",
    );
  }
  const preflightIr = TemplateDocIRSchema.parse(
    preflight.compiled.compiledDocumentIr,
  );
  if (
    templateTwinMappingsSha256(currentMappings(preflight.compiled)) !==
    input.expectedMappingsSha256
  ) {
    throw new TemplateTwinLifecycleError(
      "CONFLICT",
      "This mapping draft changed in another tab. Reload before saving.",
    );
  }
  const preflightIntents = currentExplicitFieldIntents(
    preflightIr,
    preflight.compiled,
  );
  const preflightIntentHash = explicitFieldIntentsSha256(preflightIntents);
  if (
    (preflightIntents.length > 0 && !input.expectedFieldIntentsSha256) ||
    (input.expectedFieldIntentsSha256 !== undefined &&
      preflightIntentHash !== input.expectedFieldIntentsSha256)
  ) {
    throw new TemplateTwinLifecycleError(
      "CONFLICT",
      "This field-intent draft changed in another tab. Reload before saving.",
    );
  }
  let parsedPreflightMappings: SemanticMapping[];
  try {
    parsedPreflightMappings = input.mappings.map((mapping) =>
      SemanticMappingSchema.parse(mapping),
    );
  } catch {
    throw new TemplateTwinLifecycleError(
      "MAPPING_INVALID",
      "A semantic mapping is invalid.",
    );
  }
  const compilerFieldIds = new Set(
    preflightIr.fields.map((field) => field.fieldId),
  );
  const requestedMappingIds = new Set(
    parsedPreflightMappings.map(({ fieldId }) => fieldId),
  );
  if (
    requestedMappingIds.size !== parsedPreflightMappings.length ||
    requestedMappingIds.size !== compilerFieldIds.size ||
    [...requestedMappingIds].some((fieldId) => !compilerFieldIds.has(fieldId))
  ) {
    throw new TemplateTwinLifecycleError(
      "FIELD_SET_MISMATCH",
      "Mappings must preserve the exact compiler field set.",
    );
  }
  const explicitFieldIds = new Set(
    preflightIr.fields
      .filter(fieldRequiresExplicitIntent)
      .map((field) => field.fieldId),
  );
  let parsedIntents: TemplateTwinFieldIntentInput[];
  try {
    parsedIntents = (input.fieldIntents ?? []).map((intent) =>
      TemplateTwinFieldIntentInputSchema.parse(intent),
    );
  } catch {
    throw new TemplateTwinLifecycleError(
      "MAPPING_INVALID",
      "A placeholder field intent is invalid.",
    );
  }
  const requestedIntentIds = new Set(
    parsedIntents.map(({ fieldId }) => fieldId),
  );
  if (
    requestedIntentIds.size !== parsedIntents.length ||
    requestedIntentIds.size !== explicitFieldIds.size ||
    [...requestedIntentIds].some((fieldId) => !explicitFieldIds.has(fieldId))
  ) {
    throw new TemplateTwinLifecycleError(
      "FIELD_SET_MISMATCH",
      "Field intent decisions must preserve the exact placeholder field set.",
    );
  }
  const preflightMappingById = new Map(
    parsedPreflightMappings.map((mapping) => [mapping.fieldId, mapping]),
  );
  const preflightIntentById = new Map(
    parsedIntents.map((intent) => [intent.fieldId, intent]),
  );
  for (const field of preflightIr.fields) {
    const issue = validateTemplateTwinClinicalDetail({
      field,
      mapping: preflightMappingById.get(field.fieldId)!,
      intent: preflightIntentById.get(field.fieldId),
    });
    if (issue) {
      throw new TemplateTwinLifecycleError(
        "MAPPING_INVALID",
        `Field ${issue.fieldNumber} (${issue.fieldLabel}) — ${issue.message}`,
        [issue],
      );
    }
  }
  const preflightCurrentIntentById = new Map(
    preflightIntents.map((entry) => [entry.fieldId, entry.intent]),
  );
  for (const requested of parsedIntents) {
    const current = preflightCurrentIntentById.get(requested.fieldId);
    if (!current || current.intentKind === "unresolved") continue;
    const unchanged =
      (requested.intentKind === "supported_concept" &&
        current.intentKind === "supported_concept" &&
        requested.supportedConcept === current.supportedConcept) ||
      (requested.intentKind === "static" &&
        current.intentKind === "static" &&
        requested.reason === current.reason) ||
      (requested.intentKind === "custom_concept" &&
        current.intentKind === "custom_concept" &&
        current.customSpec !== null &&
        computeTemplateFieldSpecificationContentSha256(requested.customSpec) ===
          current.customSpec.certification.contentSha256);
    if (!unchanged) {
      throw new TemplateTwinLifecycleError(
        "IMMUTABLE",
        "This field intent is already recorded for this version. Create a new draft version to change it.",
      );
    }
  }
  const requestedCustomSpecifications = parsedIntents.flatMap((intent) =>
    intent.intentKind === "custom_concept" ? [intent.customSpec] : [],
  );
  const preflightFieldById = new Map(
    preflightIr.fields.map((field) => [field.fieldId, field]),
  );
  const isStagingQaFixture =
    preflight.compiled.sourceArtifact.sha256 ===
    TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256;
  if (isStagingQaFixture) {
    const synonymMapping = parsedPreflightMappings.find(
      (mapping) => mapping.approvedSynonyms.length !== 0,
    );
    if (synonymMapping) {
      throw invalidField(
        preflightFieldById.get(synonymMapping.fieldId)!,
        "approvedSynonyms",
        "The reviewed synthetic fixture does not allow additional synonyms.",
      );
    }
    const defaultMapping = parsedPreflightMappings.find(
      (mapping) => mapping.practiceDefault !== null,
    );
    if (defaultMapping) {
      throw invalidField(
        preflightFieldById.get(defaultMapping.fieldId)!,
        "practiceDefault",
        "The reviewed synthetic fixture does not allow a practice default.",
      );
    }
    const customIntent = parsedIntents.find(
      (intent) => intent.intentKind === "custom_concept",
    );
    if (customIntent) {
      throw invalidField(
        preflightFieldById.get(customIntent.fieldId)!,
        "customConcept",
        "The reviewed synthetic fixture accepts only its allowlisted supported clinical details.",
      );
    }
    const changedStaticIntent = parsedIntents.find(
      (intent) =>
        intent.intentKind === "static" &&
        intent.reason !== TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON,
    );
    if (changedStaticIntent) {
      throw invalidField(
        preflightFieldById.get(changedStaticIntent.fieldId)!,
        "staticField",
        "Use the fixed reviewed reason when this synthetic fixture field remains static.",
      );
    }
  }

  const customIntents = parsedIntents.filter(
    (intent) => intent.intentKind === "custom_concept",
  );
  const cumulativeCustomSpecifications = requestedCustomSpecifications.slice(
    0,
    0,
  );
  for (const intent of customIntents) {
    cumulativeCustomSpecifications.push(intent.customSpec);
    try {
      assertTemplateFieldSpecificationSetWithinLimits(
        cumulativeCustomSpecifications,
      );
    } catch {
      throw invalidField(
        preflightFieldById.get(intent.fieldId)!,
        "customConcept",
        "This field makes the custom-detail set exceed the safe field, example, or text limit.",
      );
    }
  }

  const authoredGroups: Array<{
    fieldId: string;
    setting: "customConcept" | "staticField";
    fragments: string[];
    message: string;
  }> = [];
  for (const intent of parsedIntents) {
    if (intent.intentKind === "custom_concept") {
      authoredGroups.push({
        fieldId: intent.fieldId,
        setting: "customConcept",
        fragments: templateFieldSpecificationAuthoredText(intent.customSpec),
        message:
          "This custom clinical detail contains metadata or examples that did not pass the synthetic privacy check.",
      });
    }
    if (intent.intentKind === "static") {
      authoredGroups.push({
        fieldId: intent.fieldId,
        setting: "staticField",
        fragments: [intent.reason],
        message:
          "This static-field reason did not pass the synthetic privacy check.",
      });
    }
  }
  const privacyFragments = authoredGroups.flatMap((group) => group.fragments);
  try {
    await assertTemplateTwinAuthoredCorpusPhiFree({
      fragments: privacyFragments,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
      client: input.privacyClient,
    });
  } catch (error) {
    if (!(error instanceof TemplateTwinSyntheticEvidenceRejectedError)) {
      // Provider outages, invalid provider responses, and programming faults
      // are not physician mapping errors. Preserve the original failure and
      // do not multiply provider calls while trying to blame a field.
      throw error;
    }
    // The normal path keeps one bounded corpus scan. Only after it rejects do
    // we isolate the authored field so the physician gets an exact field and
    // setting instead of a generic page-level error.
    for (const group of authoredGroups) {
      try {
        await assertTemplateTwinAuthoredCorpusPhiFree({
          fragments: group.fragments,
          practiceId: input.actor.practiceId,
          userId: input.actor.userId,
          client: input.privacyClient,
        });
      } catch (groupError) {
        if (
          !(groupError instanceof TemplateTwinSyntheticEvidenceRejectedError)
        ) {
          throw groupError;
        }
        throw invalidField(
          preflightFieldById.get(group.fieldId)!,
          group.setting,
          group.message,
        );
      }
    }
    const boundaryGroup = authoredGroups.at(-1);
    if (boundaryGroup) {
      throw invalidField(
        preflightFieldById.get(boundaryGroup.fieldId)!,
        boundaryGroup.setting,
        "Adding this field makes the combined authored metadata fail the bounded synthetic privacy check.",
      );
    }
    throw new TemplateTwinLifecycleError(
      "MAPPING_INVALID",
      "The mapping draft contains invalid authored metadata.",
    );
  }
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      // Lock order is load-bearing: rollout global -> practice must precede
      // every template/configuration row touched by this final transaction.
      await assertConfigurationRolloutFinality(
        tx,
        input.actor,
        "the mapping and field intent were being saved",
      );
      const { template, compiled } = await loadOwnedCompilation(
        tx,
        input.noteTemplateId,
        input.actor,
      );
      if (
        compiled.certification ||
        compiled.certificationStatus === "CERTIFIED"
      ) {
        throw new TemplateTwinLifecycleError(
          "IMMUTABLE",
          "Certified Template Twin versions cannot be edited.",
        );
      }

      const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
      const before = currentMappings(compiled);
      const beforeHash = templateTwinMappingsSha256(before);
      if (beforeHash !== input.expectedMappingsSha256) {
        throw new TemplateTwinLifecycleError(
          "CONFLICT",
          "This mapping draft changed in another tab. Reload before saving.",
        );
      }

      const beforeIntents = currentExplicitFieldIntents(ir, compiled);
      const beforeIntentsHash = explicitFieldIntentsSha256(beforeIntents);
      if (
        (beforeIntents.length > 0 && !input.expectedFieldIntentsSha256) ||
        (input.expectedFieldIntentsSha256 !== undefined &&
          beforeIntentsHash !== input.expectedFieldIntentsSha256)
      ) {
        throw new TemplateTwinLifecycleError(
          "CONFLICT",
          "This field-intent draft changed in another tab. Reload before saving.",
        );
      }
      const fieldById = new Map(
        ir.fields.map((field) => [field.fieldId, field]),
      );
      const parsed = input.mappings.map((mapping) =>
        SemanticMappingSchema.parse(mapping),
      );
      const byId = new Map<string, SemanticMapping>();
      for (const mapping of parsed) {
        if (byId.has(mapping.fieldId)) {
          throw new TemplateTwinLifecycleError(
            "FIELD_SET_MISMATCH",
            "A field has more than one mapping.",
          );
        }
        byId.set(mapping.fieldId, mapping);
      }
      if (
        byId.size !== fieldById.size ||
        [...byId.keys()].some((fieldId) => !fieldById.has(fieldId))
      ) {
        throw new TemplateTwinLifecycleError(
          "FIELD_SET_MISMATCH",
          "Mappings must preserve the exact compiler field set.",
        );
      }

      const explicitFieldIds = new Set(
        ir.fields
          .filter(fieldRequiresExplicitIntent)
          .map((field) => field.fieldId),
      );
      const requestedIntentById = new Map(
        parsedIntents.map((intent) => [intent.fieldId, intent]),
      );
      if (
        requestedIntentById.size !== explicitFieldIds.size ||
        [...requestedIntentById.keys()].some(
          (fieldId) => !explicitFieldIds.has(fieldId),
        )
      ) {
        throw new TemplateTwinLifecycleError(
          "FIELD_SET_MISMATCH",
          "Field intent decisions must preserve the exact placeholder field set.",
        );
      }

      const now = new Date();
      const currentIntentById = new Map(
        beforeIntents.map((entry) => [entry.fieldId, entry]),
      );
      const afterIntents = [...beforeIntents];
      const newIntentRows: Array<{
        id: string;
        fieldId: string;
        definitionId: string;
        view: TemplateTwinFieldIntentView;
        customSpecJson: Prisma.InputJsonValue | undefined;
        customSpecSha256: string | null;
      }> = [];
      for (const fieldId of [...explicitFieldIds].sort()) {
        const requested = requestedIntentById.get(fieldId)!;
        const current = currentIntentById.get(fieldId)!;
        if (current.intent.intentKind !== "unresolved") {
          const unchanged =
            (requested.intentKind === "supported_concept" &&
              current.intent.intentKind === "supported_concept" &&
              requested.supportedConcept === current.intent.supportedConcept) ||
            (requested.intentKind === "static" &&
              current.intent.intentKind === "static" &&
              requested.reason === current.intent.reason) ||
            (requested.intentKind === "custom_concept" &&
              current.intent.intentKind === "custom_concept" &&
              current.intent.customSpec !== null &&
              computeTemplateFieldSpecificationContentSha256(
                requested.customSpec,
              ) === current.intent.customSpec.certification.contentSha256);
          if (!unchanged) {
            throw new TemplateTwinLifecycleError(
              "IMMUTABLE",
              "This field intent is already recorded for this version. Create a new draft version to change it.",
            );
          }
          continue;
        }
        if (requested.intentKind === "unresolved") continue;

        const id = randomUUID();
        let view: TemplateTwinFieldIntentView;
        let customSpecJson: Prisma.InputJsonValue | undefined;
        let customSpecSha256: string | null = null;
        if (requested.intentKind === "supported_concept") {
          if (!isSupportedTemplateTwinConcept(requested.supportedConcept)) {
            throw new TemplateTwinLifecycleError(
              "UNSUPPORTED_CLINICAL_CONCEPT",
              `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON}`,
            );
          }
          view = {
            intentKind: "supported_concept",
            decisionId: id,
            version: 1,
            supportedConcept: requested.supportedConcept,
            customConceptId: null,
            customSpec: null,
            reason: null,
            decidedAtIso: now.toISOString(),
            lockedInVersion: true,
          };
        } else if (requested.intentKind === "static") {
          view = {
            intentKind: "static",
            decisionId: id,
            version: 1,
            supportedConcept: null,
            customConceptId: null,
            customSpec: null,
            reason: requested.reason,
            decidedAtIso: now.toISOString(),
            lockedInVersion: true,
          };
        } else {
          const customSpec = certifyCustomFieldSpecification({
            content: requested.customSpec,
            templateLineageId: template.lineageId,
            compiledVersionId: compiled.id,
            fieldId,
            physicianUserId: input.actor.userId,
            certifiedAt: now,
          });
          customSpecSha256 = customSpec.certification.contentSha256;
          customSpecJson = asJson(customSpec);
          view = {
            intentKind: "custom_concept",
            decisionId: id,
            version: 1,
            supportedConcept: null,
            customConceptId: customSpec.conceptId,
            customSpec,
            reason: null,
            decidedAtIso: now.toISOString(),
            lockedInVersion: true,
          };
        }
        const index = afterIntents.findIndex(
          (entry) => entry.fieldId === fieldId,
        );
        afterIntents[index] = { ...current, intent: view };
        newIntentRows.push({
          id,
          fieldId,
          definitionId: current.definitionId,
          view,
          customSpecJson,
          customSpecSha256,
        });
      }

      const customSpecifications = customConceptSpecifications(afterIntents);
      const effectiveFields = fieldsWithCertifiedCustomIntent({
        fields: ir.fields,
        intents: afterIntents,
      });
      const effectiveFieldById = new Map(
        effectiveFields.map((field) => [field.fieldId, field]),
      );
      const customProviders =
        customSpecifications.length > 0
          ? [createCertifiedCustomConceptProvider(customSpecifications)]
          : [];
      const afterIntentById = new Map(
        afterIntents.map((entry) => [entry.fieldId, entry.intent]),
      );
      for (const mapping of parsed) {
        const field = effectiveFieldById.get(mapping.fieldId)!;
        const intent = afterIntentById.get(mapping.fieldId);
        const isStatic = intent?.intentKind === "static";
        const expectedConcept =
          intent?.intentKind === "supported_concept"
            ? intent.supportedConcept
            : intent?.intentKind === "custom_concept"
              ? intent.customConceptId
              : null;
        const customSpecification =
          intent?.intentKind === "custom_concept" ? intent.customSpec : null;
        const clinicalDetailIssue = validateTemplateTwinClinicalDetail({
          field,
          mapping,
          intent: intent ? { fieldId: mapping.fieldId, ...intent } : undefined,
        });
        if (clinicalDetailIssue) {
          throw new TemplateTwinLifecycleError(
            "MAPPING_INVALID",
            `Field ${clinicalDetailIssue.fieldNumber} (${clinicalDetailIssue.fieldLabel}) — ${clinicalDetailIssue.message}`,
            [clinicalDetailIssue],
          );
        }
        if (
          mapping.clinicalConcept !== null &&
          !isSupportedTemplateTwinConcept(
            mapping.clinicalConcept,
            customProviders,
          )
        ) {
          const issue = templateTwinMappingFieldError({
            field,
            setting: "clinicalDetail",
            message:
              "Choose a clinical detail supported by this Template Twin version.",
          });
          throw new TemplateTwinLifecycleError(
            "UNSUPPORTED_CLINICAL_CONCEPT",
            `Field ${issue.fieldNumber} (${issue.fieldLabel}) — ${issue.message} ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON}`,
            [issue],
          );
        }
        if (
          mapping.status === "unsupported" ||
          !isMappingTypeCompatible(field, mapping) ||
          !validPracticeDefault(field, mapping) ||
          (mapping.status === "certified" &&
            !isStatic &&
            !mapping.clinicalConcept) ||
          (intent?.intentKind === "unresolved" &&
            mapping.status === "certified") ||
          (intent &&
            intent.intentKind !== "unresolved" &&
            !isStatic &&
            mapping.clinicalConcept !== expectedConcept) ||
          (customSpecification !== null &&
            !mappingMatchesCustomSpecification(mapping, customSpecification)) ||
          (isStatic &&
            (mapping.clinicalConcept !== null ||
              mapping.required ||
              mapping.practiceDefault !== null))
        ) {
          if (mapping.status === "unsupported") {
            throw invalidField(
              field,
              "mappingStatus",
              "Resolve the unsupported mapping before confirming this field.",
            );
          }
          if (!isMappingTypeCompatible(field, mapping)) {
            throw invalidField(
              field,
              "expectedDataType",
              "The selected field type is incompatible with this Word field.",
            );
          }
          if (!validPracticeDefault(field, mapping)) {
            throw invalidField(
              field,
              "practiceDefault",
              "The default value is not valid for this field and confirmation state.",
            );
          }
          if (customSpecification !== null) {
            throw invalidField(
              field,
              "customConcept",
              "The custom clinical detail settings do not match the reviewed specification.",
            );
          }
          if (isStatic) {
            throw invalidField(
              field,
              "staticField",
              "A static field cannot have a clinical detail, required value, or practice default.",
            );
          }
          throw invalidField(
            field,
            "clinicalDetail",
            "The selected clinical detail and field intent are incompatible.",
          );
        }
      }

      const afterHash = templateTwinMappingsSha256(parsed);
      const afterIntentsHash = explicitFieldIntentsSha256(afterIntents);
      if (afterHash === beforeHash && afterIntentsHash === beforeIntentsHash)
        return;

      const persistedByFieldId = new Map(
        compiled.fields.map((field) => [field.fieldId, field]),
      );
      for (const mapping of parsed) {
        const persisted = persistedByFieldId.get(mapping.fieldId);
        if (!persisted?.mapping) {
          throw new TemplateTwinLifecycleError(
            "FIELD_SET_MISMATCH",
            "A compiled field has no persisted mapping.",
          );
        }
        const approved = mapping.status === "certified";
        await tx.templateTwinSemanticMapping.update({
          where: { id: persisted.mapping.id },
          data: {
            clinicalConcept: mapping.clinicalConcept,
            expectedDataType: mapping.expectedDataType,
            polarityBehavior: mapping.polarityBehavior,
            temporality: mapping.temporality,
            laterality: mapping.laterality,
            unitPolicy: mapping.unitPolicy,
            approvedSynonyms: asJson(mapping.approvedSynonyms),
            required: mapping.required,
            blankPolicy: mapping.blankPolicy,
            unknownPolicy: mapping.unknownPolicy,
            practiceDefault: mapping.practiceDefault,
            mappingStatus: dbStatus(mapping.status),
            approvedById: approved ? input.actor.userId : null,
            approvedAt: approved ? now : null,
          },
        });
      }

      for (const intent of newIntentRows) {
        await tx.templateTwinFieldIntentDecision.create({
          data: {
            id: intent.id,
            fieldDefinitionId: intent.definitionId,
            version: 1,
            intentKind: intent.view.intentKind.toLocaleUpperCase("en-US"),
            supportedConcept: intent.view.supportedConcept,
            customConceptId: intent.view.customConceptId,
            ...(intent.customSpecJson === undefined
              ? {}
              : { customSpec: intent.customSpecJson }),
            customSpecSha256: intent.customSpecSha256,
            reason: intent.view.reason,
            decidedById: input.actor.userId,
          },
        });
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:field-intent:${compiled.id}:${intent.fieldId}:v1`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_FIELD_INTENT_RECORDED",
          targetType: "TemplateTwinFieldDefinition",
          targetId: intent.definitionId,
          metadata: {
            compiledVersionId: compiled.id,
            templateVersion: template.version,
            fieldId: intent.fieldId,
            intentKind: intent.view.intentKind,
            customConceptId: intent.view.customConceptId,
            customSpecSha256: intent.customSpecSha256,
            fieldIntentsSha256: afterIntentsHash,
          },
        });
      }

      // A mapping change invalidates the prior synthetic proof. The immutable
      // output object remains private; no deletion is attempted from this path.
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: {
          certificationStatus:
            compiled.blockingUnsupportedCount > 0
              ? "UNSUPPORTED"
              : "NEEDS_CONFIRMATION",
          latestSyntheticTestManifest: Prisma.DbNull,
          latestTestMappingsSha256: null,
          latestTestFieldIntentsSha256: null,
          latestTestOutputObjectKey: null,
          latestTestOutputVersionId: null,
          latestTestOutputEtag: null,
          latestTestOutputSha256: null,
          latestTestStaticContentSha256: null,
          latestTestRoundTrip: Prisma.DbNull,
          latestTestVerifiedAt: null,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:mapping-updated:${compiled.id}:${afterHash}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_MAPPING_UPDATED",
        targetType: "TemplateTwinCompiledVersion",
        targetId: compiled.id,
        metadata: {
          templateVersion: template.version,
          mappingCount: parsed.length,
          certifiedMappingCount: parsed.filter(
            (mapping) => mapping.status === "certified",
          ).length,
          mappingsSha256: afterHash,
          fieldIntentsSha256: afterIntentsHash,
          fieldIntentDecisionCount: newIntentRows.length,
          rolloutGlobalGeneration:
            input.actor.rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration:
            input.actor.rolloutToken.practiceGeneration.toString(),
        },
      });
    },
    { isolationLevel: "Serializable" },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  return workspace;
}

export async function certifyAndActivateTemplateTwin(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  /** Required whenever the compiled IR contains an intent-bearing field. */
  expectedFieldIntentsSha256?: string;
  /** Required by runtime callers. Omitting it fails closed for a certifiable
   * proof, preserving safe behavior for older direct service callers. */
  expectedSyntheticTestProvenanceSha256?: string;
  optionalFieldWaivers?: readonly { fieldId: string; reason: string }[];
}): Promise<TemplateTwinWorkspace> {
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      // Certification activates a document version. Its rollout epoch is
      // revalidated under the same global -> practice locks as disable.
      await assertConfigurationRolloutFinality(
        tx,
        input.actor,
        "the template was being certified",
      );
      const { template, compiled } = await loadOwnedCompilation(
        tx,
        input.noteTemplateId,
        input.actor,
      );
      if (compiled.certification) {
        if (compiled.certificationStatus === "CERTIFIED") return;
        throw new TemplateTwinLifecycleError(
          "IMMUTABLE",
          "This certification record is immutable.",
        );
      }

      if (
        compiled.sourceArtifact.validationStatus !== "accepted" ||
        !compiled.sourceArtifact.objectVersionId?.trim() ||
        !compiled.sourceArtifact.objectEtag?.trim()
      ) {
        throw new TemplateTwinLifecycleError(
          "CERTIFICATION_BLOCKED",
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
      }
      let sourcePrivacyScanEvidenceSha256: string;
      try {
        const sourceProvenance = assertTemplateTwinSourceProvenance({
          privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
          requireBinding: true,
          boundEvidenceSha256: templateTwinSyntheticProofSourceEvidenceSha256(
            compiled.latestTestRoundTrip,
          ),
        });
        await lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
          practiceId: input.actor.practiceId,
          bindings: sourceProvenance.evidence.staticAssetApprovalBindings ?? [],
          db: tx as unknown as Parameters<
            typeof lockAndAssertTemplateTwinStaticAssetBindingsCurrent
          >[0]["db"],
        });
        sourcePrivacyScanEvidenceSha256 = sourceProvenance.evidenceSha256;
      } catch {
        throw new TemplateTwinLifecycleError(
          "CERTIFICATION_BLOCKED",
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
      }

      const mappings = currentMappings(compiled);
      const mappingHash = templateTwinMappingsSha256(mappings);
      if (mappingHash !== input.expectedMappingsSha256) {
        throw new TemplateTwinLifecycleError(
          "CONFLICT",
          "Mappings changed after the page loaded. Reload before certifying.",
        );
      }
      const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
      const explicitIntents = currentExplicitFieldIntents(ir, compiled);
      const fieldIntentsSha256 = explicitFieldIntentsSha256(explicitIntents);
      if (
        (explicitIntents.length > 0 && !input.expectedFieldIntentsSha256) ||
        (input.expectedFieldIntentsSha256 !== undefined &&
          fieldIntentsSha256 !== input.expectedFieldIntentsSha256)
      ) {
        throw new TemplateTwinLifecycleError(
          "CONFLICT",
          "Field intent changed after the page loaded. Reload before certifying.",
        );
      }
      const intentByFieldId = new Map(
        explicitIntents.map((entry) => [entry.fieldId, entry.intent]),
      );
      const customSpecifications = customConceptSpecifications(explicitIntents);
      let approvedCustomExampleProofSha256: string | null;
      try {
        approvedCustomExampleProofSha256 =
          await assertTemplateTwinCustomExamplesReadyForCertification({
            tx,
            compiledVersionId: compiled.id,
            specifications: customSpecifications,
            mappingsSha256: mappingHash,
            fieldIntentsSha256,
            physicianUserId: input.actor.userId,
          });
      } catch (error) {
        if (error instanceof TemplateTwinCustomExampleError) {
          throw new TemplateTwinLifecycleError(
            "CERTIFICATION_BLOCKED",
            error.message,
          );
        }
        throw error;
      }
      const effectiveFields = fieldsWithCertifiedCustomIntent({
        fields: ir.fields,
        intents: explicitIntents,
      });
      const effectiveFieldById = new Map(
        effectiveFields.map((field) => [field.fieldId, field]),
      );
      const customProviders =
        customSpecifications.length > 0
          ? [createCertifiedCustomConceptProvider(customSpecifications)]
          : [];
      const syntheticManifest = TemplateTwinFillManifestSchema.safeParse(
        compiled.latestSyntheticTestManifest,
      );
      const syntheticResolutions = syntheticManifest.success
        ? new Map(
            syntheticManifest.data.fields.map((field) => [
              field.fieldId,
              field,
            ]),
          )
        : new Map();
      const mappingById = new Map(
        mappings.map((mapping) => [mapping.fieldId, mapping]),
      );
      if (
        mappings.some(
          (mapping) =>
            mapping.clinicalConcept !== null &&
            !isSupportedTemplateTwinConcept(
              mapping.clinicalConcept,
              customProviders,
            ),
        )
      ) {
        throw new TemplateTwinLifecycleError(
          "UNSUPPORTED_CLINICAL_CONCEPT",
          `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON}`,
        );
      }
      const fieldsReady = ir.fields.every((field) => {
        const effectiveField = effectiveFieldById.get(field.fieldId)!;
        const mapping = mappingById.get(field.fieldId);
        const intent = intentByFieldId.get(field.fieldId);
        if (intent?.intentKind === "unresolved") return false;
        if (intent?.intentKind === "static") {
          return Boolean(
            mapping &&
            mapping.status === "certified" &&
            mapping.clinicalConcept === null &&
            isMappingTypeCompatible(effectiveField, mapping),
          );
        }
        return Boolean(
          mapping &&
          mapping.status === "certified" &&
          mapping.clinicalConcept &&
          isSupportedTemplateTwinConcept(
            mapping.clinicalConcept,
            customProviders,
          ) &&
          isMappingTypeCompatible(effectiveField, mapping) &&
          validPracticeDefault(effectiveField, mapping),
        );
      });
      const waiverTimestamp = new Date();
      const requestedWaivers = input.optionalFieldWaivers ?? [];
      const waiverEvidence = requestedWaivers.map((waiver) => ({
        fieldId: waiver.fieldId,
        mappingsSha256: mappingHash,
        waivedById: input.actor.userId,
        reason: waiver.reason.trim(),
        waivedAt: waiverTimestamp,
      }));
      const coverage = syntheticManifest.success
        ? evaluateTemplateTwinCertificationCoverage({
            fields: effectiveFields,
            mappings,
            manifest: syntheticManifest.data,
            staticFieldIds: explicitIntents.flatMap((entry) =>
              entry.intent.intentKind === "static" ? [entry.fieldId] : [],
            ),
            waivers: waiverEvidence,
            currentMappingsSha256: mappingHash,
            actorUserId: input.actor.userId,
          })
        : null;
      const certifiedBindingsReady = ir.fields.every((field) => {
        const { certifiedBindingSha256, ...binding } = field.rendererBinding;
        return (
          rendererBindingFingerprintSha256(field.fieldId, binding) ===
          certifiedBindingSha256
        );
      });
      const proofReady = Boolean(
        certifiedBindingsReady &&
        syntheticManifest.success &&
        compiled.latestTestOutputSha256 &&
        compiled.latestTestStaticContentSha256 &&
        isVerifiedSyntheticProof({
          roundTrip: compiled.latestTestRoundTrip,
          sourceSha256: compiled.sourceArtifact.sha256,
          outputSha256: compiled.latestTestOutputSha256,
          staticContentSha256: compiled.latestTestStaticContentSha256,
          expectedStaticContentSha256: ir.staticContentSha256,
          expectedFields: ir.fields.map((field) => ({
            fieldId: field.fieldId,
            partName: field.rendererBinding.partName,
            bindingPath: field.rendererBinding.path,
            canonicalBindingPath: field.rendererBinding.canonicalPath,
            bindingType: field.rendererBinding.bindingType,
            bindingProfile: field.rendererBinding.bindingProfile,
            bindingOrdinal: field.rendererBinding.ordinal,
            nativeIdentity: nativeIdentityFromRendererBinding(
              field.rendererBinding,
            ),
            sourceBindingIdentitySha256:
              field.rendererBinding.sourceBindingIdentitySha256,
            certifiedBindingSha256:
              field.rendererBinding.certifiedBindingSha256,
            tableLocation: {
              tableIndex: field.rendererBinding.tableIndex,
              rowIndex: field.rendererBinding.rowIndex,
              cellIndex: field.rendererBinding.cellIndex,
            },
            valueSha256: canonicalSha256({
              fieldId: field.fieldId,
              value: syntheticResolutions.get(field.fieldId)?.value,
            }),
            occurrences:
              field.rowPrototype &&
              Array.isArray(syntheticResolutions.get(field.fieldId)?.value)
                ? (syntheticResolutions.get(field.fieldId)!.value as unknown[])
                    .length
                : 1,
          })),
        }),
      );
      const outputArtifact = compiled.latestTestOutputObjectKey
        ? parseTemplateTwinArtifactKey(compiled.latestTestOutputObjectKey)
        : null;
      const testReady = Boolean(
        compiled.latestSyntheticTestManifest &&
        compiled.latestTestOutputObjectKey &&
        compiled.latestTestOutputVersionId &&
        compiled.latestTestOutputEtag &&
        compiled.latestTestOutputSha256 &&
        compiled.latestTestStaticContentSha256 &&
        compiled.latestTestVerifiedAt &&
        compiled.latestTestMappingsSha256 === mappingHash &&
        compiled.latestTestFieldIntentsSha256 === fieldIntentsSha256 &&
        outputArtifact?.practiceId === input.actor.practiceId &&
        outputArtifact.kind === "output" &&
        outputArtifact.sha256 === compiled.latestTestOutputSha256 &&
        isVerifiedSyntheticManifest({
          manifest: compiled.latestSyntheticTestManifest,
          outputObjectKey: compiled.latestTestOutputObjectKey,
          compiledVersionId: compiled.id,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          ir,
          effectiveFields,
          mappings,
          staticFieldIds: explicitIntents.flatMap((entry) =>
            entry.intent.intentKind === "static" ? [entry.fieldId] : [],
          ),
          conceptProviders: customProviders,
          fieldIntentsSha256,
          customSpecifications,
        }) &&
        proofReady,
      );
      if (
        !fieldsReady ||
        compiled.fields.length !== ir.fields.length ||
        compiled.blockingUnsupportedCount > 0 ||
        ir.unsupported.some((item) => item.blocksCertification) ||
        !coverage?.ready ||
        !testReady
      ) {
        const coverageIssue = coverage?.issues[0];
        throw new TemplateTwinLifecycleError(
          "CERTIFICATION_BLOCKED",
          coverageIssue
            ? `${coverageIssue.code}: ${coverageIssue.message}`
            : "Confirm every field, clear blocking structure, and verify a synthetic DOCX using the current mappings.",
        );
      }

      const syntheticTestProvenanceSha256 =
        templateTwinSyntheticTestProvenanceSha256({
          compiledVersionId: compiled.id,
          latestSyntheticTestManifest: compiled.latestSyntheticTestManifest,
          latestTestMappingsSha256: compiled.latestTestMappingsSha256,
          latestTestFieldIntentsSha256: compiled.latestTestFieldIntentsSha256,
          latestTestOutputObjectKey: compiled.latestTestOutputObjectKey,
          latestTestOutputVersionId: compiled.latestTestOutputVersionId,
          latestTestOutputEtag: compiled.latestTestOutputEtag,
          latestTestOutputSha256: compiled.latestTestOutputSha256,
          latestTestStaticContentSha256: compiled.latestTestStaticContentSha256,
          latestTestRoundTrip: compiled.latestTestRoundTrip,
          latestTestVerifiedAt: compiled.latestTestVerifiedAt,
        });
      if (
        !syntheticTestProvenanceSha256 ||
        syntheticTestProvenanceSha256 !==
          input.expectedSyntheticTestProvenanceSha256
      ) {
        throw new TemplateTwinLifecycleError(
          "CONFLICT",
          "The synthetic test changed after it was reviewed. Review the latest test output and acknowledge it again before certifying.",
        );
      }

      const persistedFieldById = new Map(
        compiled.fields.map((field) => [field.fieldId, field]),
      );
      if (waiverEvidence.length > 0) {
        await tx.templateTwinFieldTestWaiver.createMany({
          data: waiverEvidence.map((waiver) => ({
            compiledVersionId: compiled.id,
            fieldDefinitionId: persistedFieldById.get(waiver.fieldId)!.id,
            fieldId: waiver.fieldId,
            mappingsSha256: waiver.mappingsSha256,
            waivedById: waiver.waivedById,
            reason: waiver.reason,
            waivedAt: waiverTimestamp,
          })),
        });
      }
      // All mutable rows are finalized before the append-only certification is
      // inserted; database triggers reject any subsequent changes.
      await tx.templateTwinFieldDefinition.updateMany({
        where: { compiledVersionId: compiled.id },
        data: { detectionStatus: "CERTIFIED" },
      });
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: { certificationStatus: "CERTIFIED" },
      });
      await tx.noteTemplate.updateMany({
        where: {
          doctorId: input.actor.userId,
          encounterType: template.encounterType,
          status: "active",
          NOT: { id: template.id },
        },
        data: { status: "inactive" },
      });
      await tx.noteTemplate.update({
        where: { id: template.id },
        data: { status: "active" },
      });
      await tx.templateTwinCertification.create({
        data: {
          compiledVersionId: compiled.id,
          certifiedById: input.actor.userId,
          compiledStructureSha256: ir.structureSha256,
          approvedMappingsSha256: mappingHash,
          approvedFieldIntentsSha256: fieldIntentsSha256,
          approvedCustomExampleProofSha256,
          sourcePrivacyScanEvidenceSha256,
          syntheticTestManifest:
            compiled.latestSyntheticTestManifest as Prisma.InputJsonValue,
          testOutputObjectKey: compiled.latestTestOutputObjectKey!,
          testOutputVersionId: compiled.latestTestOutputVersionId!,
          testOutputEtag: compiled.latestTestOutputEtag!,
          testOutputSha256: compiled.latestTestOutputSha256!,
        },
      });

      for (const waiver of waiverEvidence) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:field-test-waived:${compiled.id}:${waiver.fieldId}:${mappingHash}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_FIELD_TEST_WAIVED",
          targetType: "TemplateTwinFieldDefinition",
          targetId: persistedFieldById.get(waiver.fieldId)!.id,
          metadata: {
            compiledVersionId: compiled.id,
            fieldId: waiver.fieldId,
            mappingsSha256: mappingHash,
            templateVersion: template.version,
          },
        });
      }

      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:certified:${compiled.id}:${mappingHash}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_CERTIFIED",
        targetType: "TemplateTwinCompiledVersion",
        targetId: compiled.id,
        metadata: {
          templateVersion: template.version,
          compilerVersion: ir.compilerVersion,
          fieldCount: ir.fields.length,
          optionalFieldWaiverCount: waiverEvidence.length,
          sourcePrivacyScanEvidenceSha256,
          mappingsSha256: mappingHash,
          fieldIntentsSha256,
          approvedCustomExampleProofSha256,
          syntheticTestProvenanceSha256,
          rolloutGlobalGeneration:
            input.actor.rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration:
            input.actor.rolloutToken.practiceGeneration.toString(),
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:activated:${template.id}:v${template.version}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_ACTIVATED",
        targetType: "NoteTemplate",
        targetId: template.id,
        metadata: {
          templateVersion: template.version,
          compiledVersionId: compiled.id,
          mappingsSha256: mappingHash,
          rolloutGlobalGeneration:
            input.actor.rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration:
            input.actor.rolloutToken.practiceGeneration.toString(),
        },
      });
    },
    { isolationLevel: "Serializable" },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  return workspace;
}
