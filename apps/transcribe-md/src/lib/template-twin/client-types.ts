import type {
  SemanticMapping,
  TemplateDocIR,
  TemplateField,
  UnsupportedElement,
} from './ir';

export interface TemplateTwinWorkspaceField {
  definitionId: string;
  field: TemplateField;
  mapping: SemanticMapping;
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
  latestSyntheticTest: {
    verifiedAtIso: string;
    outputSha256: string;
    mappingsSha256: string;
    roundTripVerified: boolean;
    layoutWarningCodes: string[];
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
