import type {
  FieldResolution,
  SemanticMapping,
  TemplateDocIR,
  TemplateField,
  UnsupportedElement,
} from "./ir";
import type { TemplateFieldSpecificationContent } from "./custom-concepts/specification";
import type { TemplateTwinFieldIntentView } from "./field-intent";
import type { TemplateTwinCustomExampleCoverage } from "./custom-concepts/example-coverage";

export interface TemplateTwinWorkspaceField {
  definitionId: string;
  field: TemplateField;
  mapping: SemanticMapping;
  /** Ordinary placeholder tokens require one explicit physician decision.
   * Other native fields retain their existing semantic-mapping workflow. */
  intent: TemplateTwinFieldIntentView;
  customConceptScaffold: Pick<
    TemplateFieldSpecificationContent,
    "templateLineageId" | "compiledVersionId" | "fieldId" | "conceptId"
  > | null;
}

export interface TemplateTwinWorkspace {
  template: {
    id: string;
    lineageId: string;
    version: number;
    name: string;
    encounterType: string | null;
    status: "draft" | "active" | "inactive";
    certificationStatus:
      | "recognized"
      | "needs_confirmation"
      | "unsupported"
      | "certified"
      | "quarantined";
  };
  source: {
    sha256: string;
    sizeBytes: number;
    mimeType: string;
    compiledAtIso: string;
    compilerVersion: string;
  };
  /** True only for the exact reviewed staging fixture SHA-256 and byte count.
   * The client may use this to render staging guidance, but every mutation
   * still independently enforces the server rollout and source admission. */
  stagingQaFixtureSource: boolean;
  stats: TemplateDocIR["stats"];
  fields: TemplateTwinWorkspaceField[];
  unsupported: UnsupportedElement[];
  mappingsSha256: string;
  fieldIntentsSha256: string;
  /** Safe, non-secret admission evidence for the physician workspace. A
   * category is never presented as passed unless that gate completed before
   * immutable source storage. */
  admissionChecks: Array<{
    id: "upload" | "malware" | "ooxml" | "privacy" | "media" | "structure";
    label: string;
    status: "passed" | "needs_review" | "blocked" | "not_attested";
    detail: string;
  }>;
  /** Separate physician-reviewed execution proof for every exact custom-field
   * positive, negative, and ambiguity example. Null when no custom field exists. */
  customExampleCoverage?: TemplateTwinCustomExampleCoverage | null;
  latestSyntheticTest: {
    provenanceSha256: string;
    verifiedAtIso: string;
    outputSha256: string;
    mappingsSha256: string;
    roundTripVerified: boolean;
    layoutWarningCodes: string[];
    fieldCoverage: Array<{
      fieldId: string;
      exercised: boolean;
      status:
        | "supported"
        | "explicitly_denied"
        | "not_mentioned"
        | "ambiguous"
        | "conflict"
        | "needs_clinician_input"
        | "approved_practice_default";
    }>;
    facts: Array<{
      factId: string;
      concept: string;
      value: string | number | boolean;
      polarity: "affirmed" | "denied" | "uncertain" | "conditional";
      evidenceQuote: string;
      audioTimestampSeconds: number | null;
      evidenceAnchorIds: string[];
      quality: {
        asr: "high" | "review" | "unknown";
        evidence: "direct" | "conflicting" | "unclear";
      };
    }>;
    fieldResults: Array<{
      fieldId: string;
      status: FieldResolution["status"];
      value: FieldResolution["value"];
      sourceFactIds: string[];
      reasonCode: string;
    }>;
    downloadUrl: string;
  } | null;
  canEdit: boolean;
}

export type TemplateTwinReviewStatus =
  | "verified"
  | "needs_review"
  | "not_mentioned"
  | "conflict"
  | "practice_default"
  | "intentionally_static"
  | "blocked";
