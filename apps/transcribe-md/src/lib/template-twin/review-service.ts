// ============================================================================
// Template Twin — physician field-review corrections and mapping-rule forks
// ----------------------------------------------------------------------------
// A correction is an explicit, append-only physician decision. It adds a
// labeled encounter fact, re-runs the independent validator, and replaces the
// output only after exact-source rendering passes round-trip verification.
// The active certified template is never mutated. An optional mapping-rule
// action forks a new uncertified draft over the same immutable source + IR.
// ============================================================================

import { randomBytes } from "node:crypto";

import {
  Prisma,
  TemplateTwinDetectionStatus,
  TemplateTwinResolutionStatus,
} from "@prisma/client";
import prisma from "@meddoc/db";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import {
  canonicalSoapSha256,
  TEMPLATE_TWIN_SOAP_BINDING_REVIEW_REASON,
} from "./soap-binding";
import type { TemplateTwinFieldCorrectionRequest } from "./contracts";
import { parseExplicitNumberAndUnit } from "./encounter-facts";
import {
  finalizeTemplateTwinFill,
  lockCurrentTemplateTwinVisit,
  visitMatchesPreparedSoap,
  type PreparedTemplateTwinFill,
} from "./fill-engine";
import {
  EncounterFactSchema,
  FieldResolutionSchema,
  SemanticMappingSchema,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinFillManifest,
} from "./ir";
import {
  createTemplateTwinArtifactStore,
  quarantineTemplateTwinObject,
  type StoredTemplateTwinArtifact,
  type TemplateTwinArtifactStore,
} from "./storage";
import { claimTemplateTwinObject } from "./storage/object-ledger";
import { validateTemplateTwin } from "./validation";
import {
  assertTemplateTwinSourceProvenance,
  TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
} from "./source-phi-evidence";
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  isSupportedTemplateTwinConcept,
  type TemplateTwinConceptProvider,
} from "./supported-concepts";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  templateTwinRolloutAuditMetadata,
  TemplateTwinRolloutError,
  type LockedTemplateTwinRolloutDecision,
  type TemplateTwinRolloutCode,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  createCertifiedCustomConceptProvider,
  isCertifiedCustomExtractionProvenanceCurrent,
  type CertifiedTemplateFieldSpecification,
} from "./custom-concepts";
import {
  customConceptSpecifications,
  fieldRequiresExplicitIntent,
  fieldsWithCertifiedCustomIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
} from "./field-intent";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaOperation,
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
  type TemplateTwinStagingQaRunGuardRow,
} from "./staging-qa-visit-guard";
import { isTemplateTwinStagingQaCorrectionValueAllowed } from "./staging-qa-values";

export interface TemplateTwinReviewActor {
  userId: string;
  userEmail: string;
  practiceId: string;
}

export class TemplateTwinReviewError extends Error {
  readonly code:
    | "NOT_FOUND"
    | "SIGNED_IMMUTABLE"
    | "OPTIMISTIC_CONFLICT"
    | "MANIFEST_INVALID"
    | "SOAP_BINDING_STALE"
    | "CORRECTION_INVALID"
    | "TEMPLATE_PROVENANCE_INVALID"
    | TemplateTwinRolloutCode;

  constructor(
    code: TemplateTwinReviewError["code"],
    message: string,
    cause?: unknown,
  ) {
    super(message, { cause });
    this.name = "TemplateTwinReviewError";
    this.code = code;
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
  mappingStatus: TemplateTwinDetectionStatus;
  proposedByModel: string | null;
  approvedById: string | null;
  approvedAt: Date | null;
}

interface PersistedFieldRow {
  id: string;
  fieldId: string;
  displayOrder: number;
  originalLabel: string;
  fieldKind: string;
  allowedOptions: unknown;
  rendererBinding: unknown;
  detectionStatus: TemplateTwinDetectionStatus;
  clinicallyMaterial: boolean;
  criticality: string;
  required: boolean;
  intentDecisions?: Array<{
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
  mapping: PersistedMappingRow | null;
}

interface OwnedReviewContext {
  id: string;
  practiceId: string;
  visitId: string;
  status: string;
  signedDecisionAt: Date | null;
  manifestVersion: number;
  fillManifest: unknown;
  resolverModelVersion: string | null;
  visit: {
    userId: string;
    status: string;
    reviewReason: string | null;
    soapFinal: string | null;
    soapVersion: number;
    templateTwinSyntheticQaRun?: TemplateTwinStagingQaRunGuardRow | null;
  };
  compiledVersion: {
    id: string;
    sourceArtifactId: string;
    compilerVersion: string;
    irSchemaVersion: number;
    compiledDocumentIr: unknown;
    unsupportedElements: unknown;
    structureSha256: string;
    staticContentSha256: string;
    certificationStatus: string;
    blockingUnsupportedCount: number;
    certification: {
      sourcePrivacyScanEvidenceSha256: string | null;
      approvedFieldIntentsSha256?: string | null;
    } | null;
    sourceArtifact: {
      practiceId: string;
      objectKey: string | null;
      objectVersionId: string | null;
      objectEtag: string | null;
      sha256: string;
      sizeBytes: number;
      validationStatus: string;
      privacyScanEvidence: unknown;
    };
    noteTemplate: {
      id: string;
      doctorId: string | null;
      name: string;
      encounterType: string | null;
      specialtyBaseline: string | null;
      sections: unknown;
      styleProfile: unknown;
      version: number;
      status: string;
      lineageId: string;
      templateKind: string;
    };
    fields: PersistedFieldRow[];
  };
}

interface MappingRuleForkPlan {
  targetFieldId: string;
  context: OwnedReviewContext;
}

interface ReviewDecisionPlan {
  fillManifestId: string;
  fieldId: string;
  fieldDefinitionId: string;
  resolutionStatus: TemplateTwinResolutionStatus;
  decisionKind: string;
  previousValue: FieldResolution["value"];
  correctedValue: FieldResolution["value"];
  sourceFactIds: string[];
  reasonCode: TemplateTwinFieldCorrectionRequest["reasonCode"];
  createMappingRule: boolean;
  expectedManifestVersion: number;
  reviewerId: string;
}

interface CommitReviewPlan {
  fillManifestId: string;
  practiceId: string;
  visitId: string;
  soapVersion: number;
  soapFinal: string;
  expectedManifestVersion: number;
  prepared: PreparedTemplateTwinFill;
  storedOutput: StoredTemplateTwinArtifact | null;
  staticContentSha256: string;
  reviewerEmail: string;
  rolloutToken: TemplateTwinRolloutToken;
  stagingQaClaim: { runId: string; attempt: number } | null;
  decision: ReviewDecisionPlan;
  fork: MappingRuleForkPlan | null;
}

interface CommitReviewResult {
  applied: boolean;
  soapBindingStale?: boolean;
  rolloutRejected?: Exclude<
    LockedTemplateTwinRolloutDecision,
    { allowed: true }
  > | null;
  manifestVersion: number | null;
  draftTemplateId: string | null;
  draftTemplateVersion: number | null;
}

export interface TemplateTwinReviewRepository {
  pinRollout(practiceId: string): Promise<TemplateTwinRolloutToken>;
  loadOwned(input: {
    visitId: string;
    actor: TemplateTwinReviewActor;
  }): Promise<OwnedReviewContext | null>;
  commit(plan: CommitReviewPlan): Promise<CommitReviewResult>;
}

export interface ReviewTemplateTwinFieldInput {
  visitId: string;
  actor: TemplateTwinReviewActor;
  correction: TemplateTwinFieldCorrectionRequest;
  validationNow?: Date | string;
}

export interface ReviewTemplateTwinFieldResult {
  fillManifestId: string;
  manifestVersion: number;
  status: "verified" | "needs_review";
  counts: TemplateTwinFillManifest["counts"];
  roundTripVerified: boolean;
  certificationUrl: string | null;
  draftTemplateVersion: number | null;
}

export interface TemplateTwinReviewServiceDependencies {
  repository?: TemplateTwinReviewRepository;
  storage?: TemplateTwinArtifactStore;
  /** Test seam; production always uses the independently validating exact
   * renderer orchestration exported by fill-engine. */
  finalizeFill?: typeof finalizeTemplateTwinFill;
  /** Returns the 24-lowercase-hex suffix of a new physician fact ID. */
  factIdFactory?: () => string;
  now?: () => Date;
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

function nullableJson(
  value: unknown,
): Prisma.InputJsonValue | typeof Prisma.JsonNull {
  return value === null ? Prisma.JsonNull : asJson(value);
}

function mappingFromRow(
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

function resolutionStatusForDb(
  status: FieldResolution["status"],
): TemplateTwinResolutionStatus {
  const statuses: Record<
    FieldResolution["status"],
    TemplateTwinResolutionStatus
  > = {
    supported: TemplateTwinResolutionStatus.SUPPORTED,
    explicitly_denied: TemplateTwinResolutionStatus.EXPLICITLY_DENIED,
    not_mentioned: TemplateTwinResolutionStatus.NOT_MENTIONED,
    ambiguous: TemplateTwinResolutionStatus.AMBIGUOUS,
    conflict: TemplateTwinResolutionStatus.CONFLICT,
    needs_clinician_input: TemplateTwinResolutionStatus.NEEDS_CLINICIAN_INPUT,
    approved_practice_default:
      TemplateTwinResolutionStatus.APPROVED_PRACTICE_DEFAULT,
  };
  return statuses[status];
}

function defaultFactIdFactory(): string {
  return randomBytes(12).toString("hex");
}

function nextFactId(factory: () => string, used: Set<string>): string {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const suffix = factory();
    if (!/^[a-f0-9]{24}$/.test(suffix)) {
      throw new TemplateTwinReviewError(
        "CORRECTION_INVALID",
        "The physician correction could not receive a valid evidence identifier.",
      );
    }
    const factId = `ttfact_${suffix}`;
    if (!used.has(factId)) {
      used.add(factId);
      return factId;
    }
  }
  throw new TemplateTwinReviewError(
    "CORRECTION_INVALID",
    "The physician correction could not receive a unique evidence identifier.",
  );
}

function strictIsoDate(value: string): boolean {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const date = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  );
  return (
    date.getUTCFullYear() === Number(match[1]) &&
    date.getUTCMonth() === Number(match[2]) - 1 &&
    date.getUTCDate() === Number(match[3])
  );
}

function lateralityFromValue(
  value: string | number | boolean,
  mapping: SemanticMapping,
): EncounterFact["laterality"] {
  if (mapping.laterality === "not_applicable") return "not_applicable";
  const text = String(value);
  if (/\b(?:bilateral|both\s+sides?)\b/i.test(text)) return "bilateral";
  const left = /\bleft\b/i.test(text);
  const right = /\bright\b/i.test(text);
  if (left && right) return "bilateral";
  if (left) return "left";
  if (right) return "right";
  if (/\bmidline\b/i.test(text)) return "midline";
  return "unknown";
}

interface CanonicalScalar {
  value: string | number | boolean;
  optionOrdinal: number | null;
}

function invalidCorrection(message: string): never {
  throw new TemplateTwinReviewError("CORRECTION_INVALID", message);
}

function canonicalScalar(
  field: TemplateField,
  mapping: SemanticMapping,
  raw: unknown,
): CanonicalScalar {
  switch (field.kind) {
    case "narrative_text": {
      if (typeof raw !== "string" || raw.trim().length === 0) {
        return invalidCorrection(
          "Enter a non-empty text value or clear the field explicitly.",
        );
      }
      return { value: raw.trim(), optionOrdinal: null };
    }
    case "single_select": {
      if (typeof raw !== "string") {
        return invalidCorrection(
          "Choose one exact option from the certified dropdown.",
        );
      }
      const candidate = raw.trim();
      const option = field.allowedOptions.find(
        (item) => item.value === candidate || item.displayText === candidate,
      );
      if (!option) {
        return invalidCorrection(
          "Choose one exact option from the certified dropdown.",
        );
      }
      return { value: option.value, optionOrdinal: option.ordinal };
    }
    case "multi_select":
      return invalidCorrection(
        "Multi-select corrections require a list of exact options.",
      );
    case "checkbox":
      if (typeof raw !== "boolean") {
        return invalidCorrection(
          "A checkbox correction must be checked or not checked.",
        );
      }
      if (
        raw === false &&
        mapping.polarityBehavior !== "explicit_denial_allowed"
      ) {
        return invalidCorrection(
          "This certified field does not define unchecked as false. Leave it unresolved or create a new certified template version.",
        );
      }
      return { value: raw, optionOrdinal: null };
    case "date": {
      if (typeof raw !== "string" || !strictIsoDate(raw.trim())) {
        return invalidCorrection(
          "Enter an unambiguous calendar date in YYYY-MM-DD format.",
        );
      }
      return { value: raw.trim(), optionOrdinal: null };
    }
    case "number":
      if (typeof raw !== "number" || !Number.isFinite(raw)) {
        return invalidCorrection(
          "Enter an explicit finite number without a unit.",
        );
      }
      return { value: raw, optionOrdinal: null };
    case "measurement": {
      if (
        (typeof raw !== "string" && typeof raw !== "number") ||
        typeof raw === "boolean"
      ) {
        return invalidCorrection(
          "Enter an explicit number and its stated unit.",
        );
      }
      const parsed = parseExplicitNumberAndUnit(raw);
      if (parsed.number === null) {
        return invalidCorrection(
          "Enter an explicit finite measurement number.",
        );
      }
      if (mapping.unitPolicy === "required" && parsed.unit === null) {
        return invalidCorrection("This measurement requires an explicit unit.");
      }
      if (mapping.unitPolicy === "forbidden" && parsed.unit !== null) {
        return invalidCorrection("This field does not permit a unit.");
      }
      return {
        value: parsed.unit ? `${parsed.number} ${parsed.unit}` : parsed.number,
        optionOrdinal: null,
      };
    }
  }
}

function canonicalRepeatingScalar(
  field: TemplateField,
  mapping: SemanticMapping,
  raw: string | null | undefined,
): CanonicalScalar {
  if (raw === null || raw === undefined || raw.trim().length === 0) {
    return invalidCorrection(
      "Every submitted repeating row requires an explicit value.",
    );
  }
  const value = raw.trim();
  if (field.kind === "number") {
    if (!/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(value)) {
      return invalidCorrection(
        "Every repeating number must be an explicit finite number.",
      );
    }
    return canonicalScalar(field, mapping, Number(value));
  }
  if (field.kind === "checkbox") {
    if (value !== "true" && value !== "false") {
      return invalidCorrection(
        "Every repeating checkbox value must be true or false.",
      );
    }
    return canonicalScalar(field, mapping, value === "true");
  }
  if (field.kind === "multi_select") {
    const option = field.allowedOptions.find(
      (item) => item.value === value || item.displayText === value,
    );
    if (!option) {
      return invalidCorrection(
        "Every repeating selection must be one exact certified option.",
      );
    }
    return { value: option.value, optionOrdinal: option.ordinal };
  }
  return canonicalScalar(field, mapping, value);
}

function physicianFact(input: {
  field: TemplateField;
  mapping: SemanticMapping;
  value: string | number | boolean;
  factId: string;
  anchorId: string;
  customSpecification?: CertifiedTemplateFieldSpecification;
}): EncounterFact {
  const numberAndUnit =
    input.field.kind === "number" || input.field.kind === "measurement"
      ? parseExplicitNumberAndUnit(input.value)
      : { number: null, unit: null };
  const customDenied =
    input.customSpecification?.polarityPolicy.allowExplicitDenial === true &&
    input.customSpecification.polarityPolicy.exactDeniedOutput === input.value;
  const checkboxDenied =
    input.field.kind === "checkbox" && input.value === false;
  const temporality = input.customSpecification
    ? input.customSpecification.allowedTemporalities[0]!
    : input.mapping.temporality === "historical" ||
        input.mapping.temporality === "planned" ||
        input.mapping.temporality === "current"
      ? input.mapping.temporality
      : "current";
  const laterality = input.customSpecification
    ? input.customSpecification.allowedLateralities[0]!
    : lateralityFromValue(input.value, input.mapping);
  return EncounterFactSchema.parse({
    factId: input.factId,
    sourceType: "clinician_correction",
    concept: input.mapping.clinicalConcept,
    value: input.value,
    polarity: checkboxDenied || customDenied ? "denied" : "affirmed",
    temporality,
    experiencer: "patient",
    laterality,
    number: numberAndUnit.number,
    unit: numberAndUnit.unit,
    speaker: "Physician correction",
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [input.anchorId],
    evidenceQuote: "Physician correction entered during Template Twin review.",
    quality: { asr: "unknown", evidence: "direct" },
  });
}

export function buildClinicianCorrection(input: {
  field: TemplateField;
  mapping: SemanticMapping;
  value: TemplateTwinFieldCorrectionRequest["value"];
  existingFactIds: ReadonlySet<string>;
  factIdFactory?: () => string;
  conceptProviders?: readonly TemplateTwinConceptProvider[];
  customSpecification?: CertifiedTemplateFieldSpecification;
}): { facts: EncounterFact[]; resolution: FieldResolution } {
  const field = input.field;
  const mapping = input.mapping;
  if (mapping.status !== "certified" || !mapping.clinicalConcept) {
    return invalidCorrection(
      "The field does not have a certified semantic mapping.",
    );
  }
  if (
    !isSupportedTemplateTwinConcept(
      mapping.clinicalConcept,
      input.conceptProviders ?? [],
    )
  ) {
    return invalidCorrection(
      `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: This field is outside the current supported clinical detail registry.`,
    );
  }
  if (input.customSpecification) {
    if (
      input.customSpecification.fieldId !== field.fieldId ||
      input.customSpecification.conceptId !== mapping.clinicalConcept
    ) {
      return invalidCorrection(
        "The custom field correction does not match its certified field specification.",
      );
    }
    if (
      input.customSpecification.allowedTemporalities.length !== 1 ||
      input.customSpecification.allowedLateralities.length !== 1
    ) {
      return invalidCorrection(
        "This custom field permits more than one time or side meaning. Record a new template version with one exact correction policy before entering a manual value.",
      );
    }
  }

  if (input.value === null) {
    const requiresInput =
      field.required ||
      mapping.required ||
      field.unknownPolicy === "requires_input" ||
      mapping.unknownPolicy === "requires_input";
    return {
      facts: [],
      resolution: FieldResolutionSchema.parse({
        fieldId: field.fieldId,
        status: requiresInput ? "needs_clinician_input" : "not_mentioned",
        value: null,
        sourceFactIds: [],
        evidenceAnchorIds: [],
        selectedOptionOrdinal: null,
        reasonCode: "clinician_cleared_field",
        clinicianReviewed: true,
      }),
    };
  }

  const used = new Set(input.existingFactIds);
  const factory = input.factIdFactory ?? defaultFactIdFactory;
  const facts: EncounterFact[] = [];
  const createFact = (value: string | number | boolean): EncounterFact => {
    const factId = nextFactId(factory, used);
    const anchorId = `clinician_review_${factId.slice("ttfact_".length)}`;
    const fact = physicianFact({
      field,
      mapping,
      value,
      factId,
      anchorId,
      customSpecification: input.customSpecification,
    });
    facts.push(fact);
    return fact;
  };

  let correctedValue: FieldResolution["value"];
  let selectedOptionOrdinal: number | null = null;

  if (field.rowPrototype) {
    if (
      !Array.isArray(input.value) ||
      input.value.length === 0 ||
      input.value.some(
        (row) => typeof row !== "object" || row === null || Array.isArray(row),
      )
    ) {
      return invalidCorrection(
        "A repeating-row correction must contain at least one row.",
      );
    }
    correctedValue = (input.value as Array<Record<string, string | null>>).map(
      (row) => {
        const canonical = canonicalRepeatingScalar(field, mapping, row.value);
        const fact = createFact(canonical.value);
        return {
          value: String(canonical.value),
          sourceFactId: fact.factId,
          evidenceAnchorId: fact.evidenceAnchorIds[0] ?? null,
          optionOrdinal:
            canonical.optionOrdinal === null
              ? null
              : String(canonical.optionOrdinal),
        };
      },
    );
  } else if (field.kind === "multi_select") {
    if (
      !Array.isArray(input.value) ||
      input.value.length === 0 ||
      input.value.some((value) => typeof value !== "string")
    ) {
      return invalidCorrection("Choose one or more exact certified options.");
    }
    const canonicalValues = (input.value as string[]).map((raw) => {
      const candidate = raw.trim();
      const option = field.allowedOptions.find(
        (item) => item.value === candidate || item.displayText === candidate,
      );
      if (!option)
        return invalidCorrection("Choose only exact certified options.");
      return option.value;
    });
    if (new Set(canonicalValues).size !== canonicalValues.length) {
      return invalidCorrection("Do not select the same option more than once.");
    }
    correctedValue = canonicalValues;
    for (const value of canonicalValues) createFact(value);
  } else {
    const canonical = canonicalScalar(field, mapping, input.value);
    correctedValue = canonical.value;
    selectedOptionOrdinal = canonical.optionOrdinal;
    createFact(canonical.value);
  }

  const customDenied =
    input.customSpecification?.polarityPolicy.allowExplicitDenial === true &&
    input.customSpecification.polarityPolicy.exactDeniedOutput ===
      correctedValue;
  const status: FieldResolution["status"] =
    (field.kind === "checkbox" && correctedValue === false) || customDenied
      ? "explicitly_denied"
      : "supported";
  return {
    facts,
    resolution: FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status,
      value: correctedValue,
      sourceFactIds: facts.map((fact) => fact.factId),
      evidenceAnchorIds: facts.flatMap((fact) => fact.evidenceAnchorIds),
      selectedOptionOrdinal,
      reasonCode: "physician_review_correction",
      clinicianReviewed: true,
    }),
  };
}

function assertProvenance(
  context: OwnedReviewContext,
  actor: TemplateTwinReviewActor,
  manifest: TemplateTwinFillManifest,
  ir: TemplateDocIR,
): void {
  const compiled = context.compiledVersion;
  if (
    context.practiceId !== actor.practiceId ||
    context.visit.userId !== actor.userId ||
    compiled.noteTemplate.doctorId !== actor.userId ||
    compiled.sourceArtifact.practiceId !== actor.practiceId ||
    compiled.noteTemplate.templateKind !== "template_twin_docx" ||
    compiled.certificationStatus !== "CERTIFIED" ||
    compiled.sourceArtifact.validationStatus !== "accepted" ||
    !compiled.sourceArtifact.objectKey ||
    !compiled.sourceArtifact.objectVersionId ||
    !compiled.sourceArtifact.objectEtag ||
    manifest.compiledVersionId !== compiled.id ||
    manifest.noteTemplateId !== compiled.noteTemplate.id ||
    manifest.noteTemplateVersion !== compiled.noteTemplate.version ||
    manifest.compilerVersion !== ir.compilerVersion
  ) {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      "The visit no longer matches its certified Template Twin provenance.",
    );
  }
  try {
    assertTemplateTwinSourceProvenance({
      privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
      requireBinding: true,
      boundEvidenceSha256:
        compiled.certification?.sourcePrivacyScanEvidenceSha256,
    });
  } catch {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
    );
  }
}

export function createTemplateTwinReviewRepository(): TemplateTwinReviewRepository {
  return {
    pinRollout(practiceId) {
      return pinTemplateTwinRollout({ practiceId });
    },

    async loadOwned(input): Promise<OwnedReviewContext | null> {
      const row = await prisma.templateTwinFillManifest.findFirst({
        where: {
          visitId: input.visitId,
          practiceId: input.actor.practiceId,
          visit: { userId: input.actor.userId },
          compiledVersion: {
            noteTemplate: { doctorId: input.actor.userId },
          },
        },
        select: {
          id: true,
          practiceId: true,
          visitId: true,
          status: true,
          signedDecisionAt: true,
          manifestVersion: true,
          fillManifest: true,
          resolverModelVersion: true,
          visit: {
            select: {
              userId: true,
              status: true,
              reviewReason: true,
              soapFinal: true,
              soapVersion: true,
              templateTwinSyntheticQaRun: {
                select: TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
              },
            },
          },
          compiledVersion: {
            select: {
              id: true,
              sourceArtifactId: true,
              compilerVersion: true,
              irSchemaVersion: true,
              compiledDocumentIr: true,
              unsupportedElements: true,
              structureSha256: true,
              staticContentSha256: true,
              certificationStatus: true,
              blockingUnsupportedCount: true,
              certification: {
                select: {
                  sourcePrivacyScanEvidenceSha256: true,
                  approvedFieldIntentsSha256: true,
                },
              },
              sourceArtifact: {
                select: {
                  practiceId: true,
                  objectKey: true,
                  objectVersionId: true,
                  objectEtag: true,
                  sha256: true,
                  sizeBytes: true,
                  validationStatus: true,
                  privacyScanEvidence: true,
                },
              },
              noteTemplate: {
                select: {
                  id: true,
                  doctorId: true,
                  name: true,
                  encounterType: true,
                  specialtyBaseline: true,
                  sections: true,
                  styleProfile: true,
                  version: true,
                  status: true,
                  lineageId: true,
                  templateKind: true,
                },
              },
              fields: {
                orderBy: { displayOrder: "asc" },
                select: {
                  id: true,
                  fieldId: true,
                  displayOrder: true,
                  originalLabel: true,
                  fieldKind: true,
                  allowedOptions: true,
                  rendererBinding: true,
                  detectionStatus: true,
                  clinicallyMaterial: true,
                  criticality: true,
                  required: true,
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
                      proposedByModel: true,
                      approvedById: true,
                      approvedAt: true,
                    },
                  },
                },
              },
            },
          },
        },
      });
      return row as unknown as OwnedReviewContext | null;
    },

    async commit(plan): Promise<CommitReviewResult> {
      return prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
            tx,
            practiceId: plan.practiceId,
            pinnedToken: plan.rolloutToken,
          });
          if (!finalRollout.allowed) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey:
                `template-twin:review-rollout-blocked:${plan.fillManifestId}` +
                `:v${plan.expectedManifestVersion}:${finalRollout.code}:` +
                `${plan.rolloutToken.globalGeneration.toString()}:` +
                plan.rolloutToken.practiceGeneration.toString(),
              practiceId: plan.practiceId,
              actorId: plan.decision.reviewerId,
              actorEmailSnapshot: plan.reviewerEmail,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TemplateTwinFillManifest",
              targetId: plan.fillManifestId,
              metadata: {
                reasonCode: finalRollout.code,
                operation: "field_correction_final_claim",
                visitId: plan.visitId,
                manifestVersion: plan.expectedManifestVersion,
                outputWrittenUnclaimed: plan.storedOutput !== null,
                ...templateTwinRolloutAuditMetadata(
                  plan.rolloutToken,
                  finalRollout.currentToken,
                ),
              },
            });
            return {
              applied: false,
              soapBindingStale: false,
              rolloutRejected: finalRollout,
              manifestVersion: null,
              draftTemplateId: null,
              draftTemplateVersion: null,
            };
          }
          if (plan.stagingQaClaim) {
            await lockAndAssertTemplateTwinStagingQaOperation({
              tx,
              runId: plan.stagingQaClaim.runId,
              expectedAttempt: plan.stagingQaClaim.attempt,
              actor: {
                userId: plan.decision.reviewerId,
                practiceId: plan.practiceId,
              },
              currentRolloutToken: finalRollout.token,
              allowedStatuses: ["COMPLETED"],
              allowedAdmissionPhases: ["REVIEW_READY"],
            });
          }
          const lockedVisit = await lockCurrentTemplateTwinVisit(
            tx,
            plan.visitId,
          );
          if (
            !visitMatchesPreparedSoap({
              visit: lockedVisit,
              doctorId: plan.decision.reviewerId,
              noteTemplateId: plan.prepared.manifest.noteTemplateId,
              noteTemplateVersion: plan.prepared.manifest.noteTemplateVersion,
              soapFinal: plan.soapFinal,
              manifest: plan.prepared.manifest,
            })
          ) {
            if (plan.storedOutput) {
              await quarantineTemplateTwinObject(tx, {
                objectKey: plan.storedOutput.objectKey,
                practiceId: plan.practiceId,
                objectVersionId: plan.storedOutput.objectVersionId,
                objectEtag: plan.storedOutput.objectEtag,
                reasonCode: "SOAP_BINDING_STALE",
              });
            }
            await tx.templateTwinFillManifest.updateMany({
              where: {
                id: plan.fillManifestId,
                practiceId: plan.practiceId,
                status: { not: "SIGNED" },
                signedDecisionAt: null,
                manifestVersion: plan.expectedManifestVersion,
                soapVersion: plan.prepared.manifest.soapVersion,
                soapSha256: plan.prepared.manifest.soapSha256,
              },
              data: {
                status: "NEEDS_REVIEW",
                reviewedAt: null,
                reviewedById: null,
                reviewedManifestVersion: null,
                reviewedManifestSha256: null,
              },
            });
            await enqueueTemplateTwinAudit(tx, {
              eventKey:
                `template-twin:soap-binding-stale-review:${plan.fillManifestId}` +
                `:v${plan.expectedManifestVersion}`,
              practiceId: plan.practiceId,
              actorId: plan.decision.reviewerId,
              actorEmailSnapshot: plan.reviewerEmail,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TemplateTwinFillManifest",
              targetId: plan.fillManifestId,
              metadata: {
                reasonCode: "SOAP_BINDING_STALE",
                visitId: plan.visitId,
                expectedSoapVersion: plan.prepared.manifest.soapVersion,
                currentSoapVersion: lockedVisit?.soapVersion ?? null,
                manifestSha256: plan.prepared.manifestSha256,
                outputQuarantined: plan.storedOutput !== null,
              },
            });
            return {
              applied: false,
              soapBindingStale: true,
              rolloutRejected: null,
              manifestVersion: null,
              draftTemplateId: null,
              draftTemplateVersion: null,
            };
          }
          const status = plan.prepared.render ? "VERIFIED" : "NEEDS_REVIEW";
          const updated = await tx.templateTwinFillManifest.updateMany({
            where: {
              id: plan.fillManifestId,
              practiceId: plan.practiceId,
              manifestVersion: plan.expectedManifestVersion,
              status: { not: "SIGNED" },
              signedDecisionAt: null,
              visit: { is: { soapVersion: plan.soapVersion } },
            },
            data: {
              status,
              fillManifest: asJson(plan.prepared.manifest),
              manifestVersion: { increment: 1 },
              manifestSha256: plan.prepared.manifestSha256,
              factSetSha256: plan.prepared.factSetSha256,
              validationResult: asJson(plan.prepared.manifest.validation),
              filledCount: plan.prepared.manifest.counts.filled,
              needsReviewCount: plan.prepared.manifest.counts.needsReview,
              notMentionedCount: plan.prepared.manifest.counts.notMentioned,
              conflictCount: plan.prepared.manifest.counts.conflicts,
              criticalUnresolvedCount:
                plan.prepared.manifest.counts.criticalUnresolved,
              outputObjectKey: plan.storedOutput?.objectKey ?? null,
              outputVersionId: plan.storedOutput?.objectVersionId ?? null,
              outputEtag: plan.storedOutput?.objectEtag ?? null,
              outputSha256: plan.storedOutput?.sha256 ?? null,
              outputMimeType: plan.storedOutput?.mimeType ?? null,
              outputSizeBytes: plan.storedOutput?.sizeBytes ?? null,
              staticContentSha256: plan.prepared.render
                ? plan.staticContentSha256
                : null,
              roundTripVerified:
                plan.prepared.render?.verification.verified === true,
              roundTripVerification: plan.prepared.render
                ? asJson(plan.prepared.render.verification)
                : Prisma.JsonNull,
              pinnedGlobalRolloutGeneration: plan.rolloutToken.globalGeneration,
              pinnedPracticeRolloutGeneration:
                plan.rolloutToken.practiceGeneration,
              signedGlobalRolloutGeneration: null,
              signedPracticeRolloutGeneration: null,
              // A field correction creates a new immutable manifest version.
              // It is not a whole-document acknowledgement; the physician
              // must explicitly confirm the regenerated manifest afterward.
              reviewedAt: null,
              reviewedById: null,
              reviewedManifestVersion: null,
              reviewedManifestSha256: null,
            },
          });
          if (updated.count !== 1) {
            return {
              applied: false,
              soapBindingStale: false,
              rolloutRejected: null,
              manifestVersion: null,
              draftTemplateId: null,
              draftTemplateVersion: null,
            };
          }

          await tx.templateTwinReviewDecision.create({
            data: {
              fillManifestId: plan.decision.fillManifestId,
              fieldId: plan.decision.fieldId,
              fieldDefinitionId: plan.decision.fieldDefinitionId,
              resolutionStatus: plan.decision.resolutionStatus,
              decisionKind: plan.decision.decisionKind,
              previousValue: nullableJson(plan.decision.previousValue),
              correctedValue: nullableJson(plan.decision.correctedValue),
              sourceFactIds: asJson(plan.decision.sourceFactIds),
              reasonCode: plan.decision.reasonCode,
              createMappingRule: plan.decision.createMappingRule,
              expectedManifestVersion: plan.decision.expectedManifestVersion,
              reviewerId: plan.decision.reviewerId,
            },
          });

          let draftTemplateId: string | null = null;
          let draftTemplateVersion: number | null = null;
          if (plan.fork) {
            const source = plan.fork.context.compiledVersion;
            const template = source.noteTemplate;
            const latest = await tx.noteTemplate.findFirst({
              where: { lineageId: template.lineageId },
              orderBy: { version: "desc" },
              select: { version: true },
            });
            draftTemplateVersion = (latest?.version ?? template.version) + 1;
            const draft = await tx.noteTemplate.create({
              data: {
                doctorId: template.doctorId,
                name: template.name,
                encounterType: template.encounterType,
                specialtyBaseline: template.specialtyBaseline,
                sections: asJson(template.sections),
                ...(template.styleProfile === null
                  ? {}
                  : { styleProfile: asJson(template.styleProfile) }),
                version: draftTemplateVersion,
                status: "draft",
                isSystemDefault: false,
                lineageId: template.lineageId,
                parentVersionId: template.id,
                templateKind: "template_twin_docx",
                templateTwinCompiledVersion: {
                  create: {
                    sourceArtifactId: source.sourceArtifactId,
                    compilerVersion: source.compilerVersion,
                    irSchemaVersion: source.irSchemaVersion,
                    compiledDocumentIr: asJson(source.compiledDocumentIr),
                    unsupportedElements: asJson(source.unsupportedElements),
                    structureSha256: source.structureSha256,
                    staticContentSha256: source.staticContentSha256,
                    certificationStatus:
                      source.blockingUnsupportedCount > 0
                        ? "UNSUPPORTED"
                        : "NEEDS_CONFIRMATION",
                    blockingUnsupportedCount: source.blockingUnsupportedCount,
                    fields: {
                      create: source.fields.map((field) => {
                        if (!field.mapping) {
                          throw new TemplateTwinReviewError(
                            "TEMPLATE_PROVENANCE_INVALID",
                            "The certified mapping set is incomplete.",
                          );
                        }
                        const target =
                          field.fieldId === plan.fork!.targetFieldId;
                        return {
                          fieldId: field.fieldId,
                          displayOrder: field.displayOrder,
                          originalLabel: field.originalLabel,
                          fieldKind: field.fieldKind,
                          ...(field.allowedOptions === null
                            ? {}
                            : { allowedOptions: asJson(field.allowedOptions) }),
                          rendererBinding: asJson(field.rendererBinding),
                          detectionStatus: field.detectionStatus,
                          clinicallyMaterial: field.clinicallyMaterial,
                          criticality: field.criticality,
                          required: field.required,
                          mapping: {
                            create: {
                              clinicalConcept: field.mapping.clinicalConcept,
                              expectedDataType: field.mapping.expectedDataType,
                              polarityBehavior: field.mapping.polarityBehavior,
                              temporality: field.mapping.temporality,
                              laterality: field.mapping.laterality,
                              unitPolicy: field.mapping.unitPolicy,
                              approvedSynonyms: asJson(
                                field.mapping.approvedSynonyms,
                              ),
                              required: field.mapping.required,
                              blankPolicy: field.mapping.blankPolicy,
                              unknownPolicy: field.mapping.unknownPolicy,
                              practiceDefault: field.mapping.practiceDefault,
                              mappingStatus: target
                                ? TemplateTwinDetectionStatus.NEEDS_CONFIRMATION
                                : field.mapping.mappingStatus,
                              proposedByModel: field.mapping.proposedByModel,
                              approvedById: target
                                ? null
                                : field.mapping.approvedById,
                              approvedAt: target
                                ? null
                                : field.mapping.approvedAt,
                            },
                          },
                        };
                      }),
                    },
                  },
                },
              },
              select: { id: true, version: true },
            });
            draftTemplateId = draft.id;
            draftTemplateVersion = draft.version;
          }

          if (plan.storedOutput) {
            await claimTemplateTwinObject(tx, {
              objectKey: plan.storedOutput.objectKey,
              practiceId: plan.practiceId,
              claimType: "fill_manifest",
              claimId: plan.fillManifestId,
            });
          }

          // This event is clinical/audit critical. Enqueue it in the same
          // database transaction as the immutable correction decision so
          // an audit outage can never leave an unaudited physician delta.
          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin:field-reviewed:${plan.fillManifestId}:v${plan.expectedManifestVersion + 1}`,
            practiceId: plan.practiceId,
            actorId: plan.decision.reviewerId,
            actorEmailSnapshot: plan.reviewerEmail,
            action: "TEMPLATE_TWIN_FIELD_REVIEWED",
            targetType: "TemplateTwinFillManifest",
            targetId: plan.fillManifestId,
            metadata: {
              visitId: plan.visitId,
              fieldId: plan.decision.fieldId,
              decisionKind: plan.decision.decisionKind,
              resolutionStatus: plan.decision.resolutionStatus,
              manifestVersion: plan.expectedManifestVersion + 1,
              validationPassed: plan.prepared.manifest.validation.valid,
              roundTripVerified:
                plan.prepared.render?.verification.verified === true,
              mappingRuleDraftCreated: draftTemplateId !== null,
              outputSha256: plan.storedOutput?.sha256 ?? null,
              outputVersionId: plan.storedOutput?.objectVersionId ?? null,
              outputEtag: plan.storedOutput?.objectEtag ?? null,
              manifestSha256: plan.prepared.manifestSha256,
            },
          });

          return {
            applied: true,
            soapBindingStale: false,
            rolloutRejected: null,
            manifestVersion: plan.expectedManifestVersion + 1,
            draftTemplateId,
            draftTemplateVersion,
          };
        },
        // A mapping-rule fork creates compiled lineage. Database lineage
        // triggers require READ COMMITTED so their post-lock ownership reads
        // cannot retain a stale transaction snapshot. Exact manifest/SOAP
        // predicates and row locks above still make concurrent reviews lose
        // closed.
        { isolationLevel: "ReadCommitted" },
      );
    },
  };
}

export async function reviewTemplateTwinField(
  input: ReviewTemplateTwinFieldInput,
  dependencies: TemplateTwinReviewServiceDependencies = {},
): Promise<ReviewTemplateTwinFieldResult> {
  const repository =
    dependencies.repository ?? createTemplateTwinReviewRepository();
  const context = await repository.loadOwned({
    visitId: input.visitId,
    actor: input.actor,
  });
  if (!context) {
    throw new TemplateTwinReviewError(
      "NOT_FOUND",
      "Template Twin review was not found.",
    );
  }
  let rolloutToken: TemplateTwinRolloutToken;
  try {
    rolloutToken = await repository.pinRollout(input.actor.practiceId);
  } catch (error) {
    if (error instanceof TemplateTwinRolloutError) {
      throw new TemplateTwinReviewError(error.code, error.message, error);
    }
    throw error;
  }
  assertTemplateTwinStagingQaVisitGuard({
    run: context.visit.templateTwinSyntheticQaRun,
    actor: input.actor,
    currentRolloutToken: rolloutToken,
    allowedAdmissionPhases: ["REVIEW_READY"],
  });
  if (
    context.status === "SIGNED" ||
    context.signedDecisionAt !== null ||
    context.visit.status === "SIGNED"
  ) {
    throw new TemplateTwinReviewError(
      "SIGNED_IMMUTABLE",
      "A signed Template Twin manifest cannot be corrected.",
    );
  }
  if (context.manifestVersion !== input.correction.expectedManifestVersion) {
    throw new TemplateTwinReviewError(
      "OPTIMISTIC_CONFLICT",
      "This Template Twin review changed in another tab. Reload before correcting it.",
    );
  }

  const parsedManifest = TemplateTwinFillManifestSchema.safeParse(
    context.fillManifest,
  );
  if (!parsedManifest.success) {
    throw new TemplateTwinReviewError(
      "MANIFEST_INVALID",
      "The persisted Template Twin manifest failed integrity validation.",
    );
  }
  const manifest = parsedManifest.data;
  if (
    context.visit.soapVersion !== manifest.soapVersion ||
    typeof context.visit.soapFinal !== "string" ||
    canonicalSoapSha256(context.visit.soapFinal) !== manifest.soapSha256
  ) {
    throw new TemplateTwinReviewError(
      "SOAP_BINDING_STALE",
      TEMPLATE_TWIN_SOAP_BINDING_REVIEW_REASON,
    );
  }
  const ir = TemplateDocIRSchema.parse(
    context.compiledVersion.compiledDocumentIr,
  );
  assertProvenance(context, input.actor, manifest, ir);

  const persistedFields = new Map(
    context.compiledVersion.fields.map((field) => [field.fieldId, field]),
  );
  const mappings = context.compiledVersion.fields.map((field) => {
    if (!field.mapping) {
      throw new TemplateTwinReviewError(
        "TEMPLATE_PROVENANCE_INVALID",
        "The certified Template Twin mapping set is incomplete.",
      );
    }
    return mappingFromRow(field.fieldId, field.mapping);
  });
  if (
    mappings.length !== ir.fields.length ||
    ir.fields.some((field) => {
      const persisted = persistedFields.get(field.fieldId);
      return (
        !persisted ||
        persisted.detectionStatus !== TemplateTwinDetectionStatus.CERTIFIED
      );
    })
  ) {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      "The certified Template Twin field set has drifted.",
    );
  }
  const certifiedFieldIds = ir.fields.map((field) => field.fieldId);

  let explicitIntents: Array<{
    fieldId: string;
    intent: ReturnType<typeof unresolvedFieldIntent>;
  }>;
  try {
    explicitIntents = ir.fields
      .filter(fieldRequiresExplicitIntent)
      .map((definition) => {
        const persisted = persistedFields.get(definition.fieldId);
        if (!persisted) throw new Error("missing field definition");
        const decision = persisted.intentDecisions?.[0];
        return {
          fieldId: definition.fieldId,
          intent: decision
            ? parsePersistedFieldIntent({
                ...decision,
                fieldDefinitionId: persisted.id,
                fieldId: definition.fieldId,
              } satisfies PersistedTemplateTwinFieldIntent)
            : unresolvedFieldIntent(),
        };
      });
  } catch {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      "The certified placeholder intent set is invalid.",
    );
  }
  const fieldIntentsSha256 = templateTwinFieldIntentsSha256(explicitIntents);
  if (
    explicitIntents.length > 0 &&
    (explicitIntents.some(
      (entry) => entry.intent.intentKind === "unresolved",
    ) ||
      !manifest.fieldIntentsSha256 ||
      manifest.fieldIntentsSha256 !== fieldIntentsSha256 ||
      context.compiledVersion.certification?.approvedFieldIntentsSha256 !==
        fieldIntentsSha256)
  ) {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      "The certified placeholder intents no longer match this reviewed output.",
    );
  }
  const customSpecifications = customConceptSpecifications(explicitIntents);
  if (
    !isCertifiedCustomExtractionProvenanceCurrent({
      specifications: customSpecifications,
      provenance: manifest.customExtraction,
    })
  ) {
    throw new TemplateTwinReviewError(
      "TEMPLATE_PROVENANCE_INVALID",
      "The custom-field extraction proof no longer matches this certified template version.",
    );
  }
  const conceptProviders =
    customSpecifications.length > 0
      ? [createCertifiedCustomConceptProvider(customSpecifications)]
      : [];
  const staticFieldIds = explicitIntents.flatMap((entry) =>
    entry.intent.intentKind === "static" ? [entry.fieldId] : [],
  );
  const effectiveFields = fieldsWithCertifiedCustomIntent({
    fields: ir.fields,
    intents: explicitIntents,
  });

  const field = effectiveFields.find(
    (candidate) => candidate.fieldId === input.correction.fieldId,
  );
  const fieldRow = persistedFields.get(input.correction.fieldId);
  const mapping = mappings.find(
    (candidate) => candidate.fieldId === input.correction.fieldId,
  );
  const previousResolution = manifest.fields.find(
    (candidate) => candidate.fieldId === input.correction.fieldId,
  );
  if (!field || !fieldRow || !mapping || !previousResolution) {
    throw new TemplateTwinReviewError(
      "CORRECTION_INVALID",
      "The requested field is not part of this certified document version.",
    );
  }

  const oldFacts = new Map(manifest.facts.map((fact) => [fact.factId, fact]));
  const fieldEvidenceIds = new Set(previousResolution.sourceFactIds);
  if (
    input.correction.sourceFactIds.some(
      (factId) => !oldFacts.has(factId) || !fieldEvidenceIds.has(factId),
    )
  ) {
    throw new TemplateTwinReviewError(
      "CORRECTION_INVALID",
      "A selected evidence reference is not attached to this field resolution.",
    );
  }
  if (
    context.visit.templateTwinSyntheticQaRun &&
    (!isTemplateTwinStagingQaCorrectionValueAllowed(input.correction.value) ||
      input.correction.createMappingRule)
  ) {
    throw new TemplateTwinReviewError(
      "CORRECTION_INVALID",
      "Synthetic QA accepts only reviewed fixture values and cannot create a reusable mapping rule.",
    );
  }
  const correction = buildClinicianCorrection({
    field,
    mapping,
    value: input.correction.value,
    existingFactIds: new Set(oldFacts.keys()),
    factIdFactory: dependencies.factIdFactory,
    conceptProviders,
    customSpecification: customSpecifications.find(
      (specification) => specification.fieldId === field.fieldId,
    ),
  });
  const facts = [...manifest.facts, ...correction.facts];
  const resolutions = manifest.fields.map((resolution) =>
    resolution.fieldId === field.fieldId ? correction.resolution : resolution,
  );
  const validationNow =
    input.validationNow ?? dependencies.now?.() ?? new Date();
  const validation = validateTemplateTwin({
    fields: effectiveFields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds,
    staticFieldIds,
    conceptProviders,
    customSpecifications,
    now: validationNow,
  });
  const invalidCorrectionIssues = validation.issues.filter(
    (issue) => issue.fieldId === field.fieldId && issue.severity === "blocking",
  );
  if (input.correction.value !== null && invalidCorrectionIssues.length > 0) {
    throw new TemplateTwinReviewError(
      "CORRECTION_INVALID",
      invalidCorrectionIssues[0]?.message ?? "The corrected field is invalid.",
    );
  }

  const storage = dependencies.storage ?? createTemplateTwinArtifactStore();
  let source: Uint8Array | undefined;
  if (validation.valid) {
    source = await storage.readSourceArtifact({
      practiceId: input.actor.practiceId,
      objectKey: context.compiledVersion.sourceArtifact.objectKey!,
      expectedObjectVersionId:
        context.compiledVersion.sourceArtifact.objectVersionId!,
      expectedObjectEtag: context.compiledVersion.sourceArtifact.objectEtag!,
      expectedSha256: context.compiledVersion.sourceArtifact.sha256,
      expectedSizeBytes: context.compiledVersion.sourceArtifact.sizeBytes,
    });
  }
  const finalizeFill = dependencies.finalizeFill ?? finalizeTemplateTwinFill;
  const prepared = await finalizeFill({
    soapVersion: manifest.soapVersion,
    soapFinal: context.visit.soapFinal,
    compiledVersionId: context.compiledVersion.id,
    noteTemplateId: context.compiledVersion.noteTemplate.id,
    noteTemplateVersion: context.compiledVersion.noteTemplate.version,
    ir,
    mappings,
    facts,
    certifiedFieldIds,
    fieldIntentsSha256:
      explicitIntents.length > 0
        ? fieldIntentsSha256
        : manifest.fieldIntentsSha256,
    staticFieldIds,
    conceptProviders,
    customExtraction: manifest.customExtraction,
    effectiveFields,
    customSpecifications,
    resolutions,
    source,
    resolverModelVersion: context.resolverModelVersion,
    validationNow,
  });
  if (prepared.manifest.validation.valid !== validation.valid) {
    throw new TemplateTwinReviewError(
      "MANIFEST_INVALID",
      "The correction validation result was not reproducible.",
    );
  }

  const storedOutput = prepared.render
    ? await storage.storeOutputArtifact({
        practiceId: input.actor.practiceId,
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        bytes: prepared.render.document,
      })
    : null;

  const committed = await repository.commit({
    fillManifestId: context.id,
    practiceId: input.actor.practiceId,
    visitId: input.visitId,
    soapVersion: manifest.soapVersion,
    soapFinal: context.visit.soapFinal,
    expectedManifestVersion: input.correction.expectedManifestVersion,
    prepared,
    storedOutput,
    staticContentSha256: ir.staticContentSha256,
    reviewerEmail: input.actor.userEmail,
    rolloutToken,
    stagingQaClaim: context.visit.templateTwinSyntheticQaRun
      ? {
          runId: context.visit.templateTwinSyntheticQaRun.id,
          attempt: context.visit.templateTwinSyntheticQaRun.attempt,
        }
      : null,
    decision: {
      fillManifestId: context.id,
      fieldId: field.fieldId,
      fieldDefinitionId: fieldRow.id,
      resolutionStatus: resolutionStatusForDb(correction.resolution.status),
      decisionKind:
        input.correction.value === null
          ? "clinician_clear"
          : "clinician_correction",
      previousValue: previousResolution.value,
      correctedValue: correction.resolution.value,
      sourceFactIds: [
        ...input.correction.sourceFactIds,
        ...correction.facts.map((fact) => fact.factId),
      ],
      reasonCode: input.correction.reasonCode,
      createMappingRule: input.correction.createMappingRule,
      expectedManifestVersion: input.correction.expectedManifestVersion,
      reviewerId: input.actor.userId,
    },
    fork: input.correction.createMappingRule
      ? { targetFieldId: field.fieldId, context }
      : null,
  });
  if (committed.soapBindingStale) {
    throw new TemplateTwinReviewError(
      "SOAP_BINDING_STALE",
      TEMPLATE_TWIN_SOAP_BINDING_REVIEW_REASON,
    );
  }
  if (committed.rolloutRejected) {
    throw new TemplateTwinReviewError(
      committed.rolloutRejected.code,
      committed.rolloutRejected.reason,
    );
  }
  if (!committed.applied || committed.manifestVersion === null) {
    // A put-once output may have won the race before this conflict. It remains
    // an immutable, unreferenced tenant object for Operations reconciliation;
    // the clinical DB state and prior output were not changed.
    throw new TemplateTwinReviewError(
      "OPTIMISTIC_CONFLICT",
      "This Template Twin review changed in another tab. Reload before correcting it.",
    );
  }

  return {
    fillManifestId: context.id,
    manifestVersion: committed.manifestVersion,
    status: prepared.render ? "verified" : "needs_review",
    counts: prepared.manifest.counts,
    roundTripVerified: prepared.render?.verification.verified === true,
    certificationUrl: committed.draftTemplateId
      ? `/settings/note-format/${encodeURIComponent(committed.draftTemplateId)}/certify`
      : null,
    draftTemplateVersion: committed.draftTemplateVersion,
  };
}
