import { canonicalSha256 } from "./canonical";
import { isCertifiedCustomExtractionProvenanceCurrent } from "./custom-concepts";
import type { CertifiedTemplateFieldSpecification } from "./custom-concepts/specification";
import type {
  EncounterFact,
  FieldResolution,
  TemplateTwinFillManifest,
} from "./ir";

export const TEMPLATE_TWIN_CUSTOM_OUTCOME_PROOF_VERSION =
  "template-twin-custom-outcome-proof/1.0.0" as const;

export interface CustomOutcomeProofIssue {
  readonly fieldId: string | null;
  readonly code:
    | "CUSTOM_EXTRACTION_OUTCOME_PROOF_INVALID"
    | "CUSTOM_EXTRACTION_REVIEW_REQUIRED";
  readonly message: string;
}

function isPhysicianCorrection(input: {
  resolution: FieldResolution | undefined;
  factById: ReadonlyMap<string, EncounterFact>;
}): boolean {
  const { resolution } = input;
  return Boolean(
    resolution?.clinicianReviewed &&
    resolution.value !== null &&
    resolution.sourceFactIds.length > 0 &&
    resolution.sourceFactIds.every(
      (factId) =>
        input.factById.get(factId)?.sourceType === "clinician_correction",
    ),
  );
}

function expectedResolutionStatus(
  status: NonNullable<
    TemplateTwinFillManifest["customExtraction"]
  >["fields"][number]["status"],
  specification: CertifiedTemplateFieldSpecification,
): FieldResolution["status"] {
  if (status === "unknown" || status === "ambiguous") return "ambiguous";
  if (
    status === "not_mentioned" &&
    (specification.required || specification.unknownPolicy === "requires_input")
  ) {
    return "needs_clinician_input";
  }
  return status;
}

/**
 * Independently proves that every certified custom field has exactly one
 * persisted extractor outcome and that an unresolved outcome has not been
 * converted into a renderable value without an explicit physician correction.
 * This runs during fill construction, correction, and signing.
 */
export function verifyCustomExtractionOutcomeProof(input: {
  specifications: readonly CertifiedTemplateFieldSpecification[];
  proof: TemplateTwinFillManifest["customExtraction"];
  resolutions: readonly FieldResolution[];
  facts: readonly EncounterFact[];
}): readonly CustomOutcomeProofIssue[] {
  const issues: CustomOutcomeProofIssue[] = [];
  const invalid = (fieldId: string | null, message: string) =>
    issues.push({
      fieldId,
      code: "CUSTOM_EXTRACTION_OUTCOME_PROOF_INVALID",
      message,
    });
  if (input.specifications.length === 0) {
    if (input.proof !== null) {
      invalid(
        null,
        "Custom extraction evidence exists without a certified custom field specification.",
      );
    }
    return issues;
  }
  if (
    !input.proof ||
    !isCertifiedCustomExtractionProvenanceCurrent({
      specifications: input.specifications,
      provenance: input.proof,
    })
  ) {
    invalid(
      null,
      "The custom extraction contract does not match this certified template version.",
    );
    return issues;
  }
  const expected = new Map(
    input.specifications.map((specification) => [
      specification.fieldId,
      specification,
    ]),
  );
  const outcomeById = new Map(
    input.proof.fields.map((outcome) => [outcome.fieldId, outcome]),
  );
  if (
    outcomeById.size !== input.proof.fields.length ||
    outcomeById.size !== expected.size ||
    input.proof.fields.some(
      (outcome) =>
        expected.get(outcome.fieldId)?.conceptId !== outcome.conceptId,
    ) ||
    input.proof.blocksSigning !==
      input.proof.fields.some((outcome) => outcome.blocksSigning)
  ) {
    invalid(
      null,
      "The custom extraction result does not match the exact certified field set.",
    );
    return issues;
  }
  const resolutionById = new Map(
    input.resolutions.map((resolution) => [resolution.fieldId, resolution]),
  );
  const factById = new Map(input.facts.map((fact) => [fact.factId, fact]));
  for (const specification of input.specifications) {
    const outcome = outcomeById.get(specification.fieldId);
    const resolution = resolutionById.get(specification.fieldId);
    if (!outcome || !resolution) {
      invalid(
        specification.fieldId,
        "A certified custom field is missing its outcome or resolution proof.",
      );
      continue;
    }
    const corrected = isPhysicianCorrection({ resolution, factById });
    const unresolved = [
      "not_mentioned",
      "unknown",
      "ambiguous",
      "conflict",
    ].includes(outcome.status);
    const expectedBlocks =
      outcome.status === "ambiguous" ||
      outcome.status === "conflict" ||
      (unresolved &&
        (specification.required ||
          specification.unknownPolicy === "requires_input"));
    const expectedNeedsReview =
      outcome.status === "supported" || outcome.status === "explicitly_denied"
        ? false
        : outcome.status !== "not_mentioned" || expectedBlocks;
    const expectedReason =
      outcome.status === "supported"
        ? "TT_CUSTOM_SUPPORTED_V1"
        : outcome.status === "explicitly_denied"
          ? "TT_CUSTOM_EXPLICIT_DENIAL_V1"
          : `TT_CUSTOM_${outcome.status.toLocaleUpperCase("en-US")}_V1`;
    if (
      outcome.blocksSigning !== expectedBlocks ||
      outcome.needsClinicianReview !== expectedNeedsReview ||
      outcome.reasonCode !== expectedReason ||
      outcome.sourceFactIds.some(
        (factId) => factById.get(factId)?.concept !== specification.conceptId,
      )
    ) {
      invalid(
        specification.fieldId,
        "A custom extraction outcome conflicts with its certified field policy or evidence.",
      );
      continue;
    }
    if (!corrected) {
      if (
        resolution.status !==
          expectedResolutionStatus(outcome.status, specification) ||
        canonicalSha256(resolution.sourceFactIds) !==
          canonicalSha256(outcome.sourceFactIds) ||
        canonicalSha256(resolution.evidenceAnchorIds) !==
          canonicalSha256(outcome.evidenceAnchorIds)
      ) {
        invalid(
          specification.fieldId,
          "A custom field resolution no longer matches its output-derived extraction outcome.",
        );
        continue;
      }
    }
    if (outcome.blocksSigning && !corrected) {
      issues.push({
        fieldId: specification.fieldId,
        code: "CUSTOM_EXTRACTION_REVIEW_REQUIRED",
        message:
          "This custom field is uncertain or conflicting and requires an explicit physician correction.",
      });
    }
  }
  return issues;
}
