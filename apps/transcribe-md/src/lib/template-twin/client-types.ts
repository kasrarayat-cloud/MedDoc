import type {
  SemanticMapping,
  TemplateDocIR,
  TemplateField,
  UnsupportedElement,
} from './ir';
import type {
  TemplateFieldSpecificationContent,
} from './custom-concepts/specification';
import type { TemplateTwinFieldIntentView } from './field-intent';
import type { TemplateTwinCustomExampleCoverage } from './custom-concepts/example-coverage';

export interface TemplateTwinWorkspaceField {
  definitionId: string;
  field: TemplateField;
  mapping: SemanticMapping;
  /** Ordinary placeholder tokens require one explicit physician decision.
   * Other native fields retain their existing semantic-mapping workflow. */
  intent: TemplateTwinFieldIntentView;
  customConceptScaffold: Pick<
    TemplateFieldSpecificationContent,
    'templateLineageId' | 'compiledVersionId' | 'fieldId' | 'conceptId'
  > | null;
}

export interface TemplateTwinWorkspace {
  template: {
    id: string;
    lineageId: string;
    version: number;
    name: string;
    encounterType: string | null;
    status: 'draft' | 'active' | 'inactive';
    certificationStatus:
      | 'recognized'
      | 'needs_confirmation'
      | 'unsupported'
      | 'certified'
      | 'quarantined';
  };
  source: {
    sha256: string;
    sizeBytes: number;
    mimeType: string;
    compiledAtIso: string;
    compilerVersion: string;
  };
  stats: TemplateDocIR['stats'];
  fields: TemplateTwinWorkspaceField[];
  unsupported: UnsupportedElement[];
  mappingsSha256: string;
  fieldIntentsSha256: string;
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
        | 'supported'
        | 'explicitly_denied'
        | 'not_mentioned'
        | 'ambiguous'
        | 'conflict'
        | 'needs_clinician_input'
        | 'approved_practice_default';
    }>;
    downloadUrl: string;
  } | null;
  canEdit: boolean;
}

export type TemplateTwinReviewStatus =
  | 'verified'
  | 'needs_review'
  | 'not_mentioned'
  | 'conflict'
  | 'practice_default';
