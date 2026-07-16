import { canonicalSha256 } from './canonical';
import {
  SemanticMappingSchema,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  TemplateTwinValidationResultSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
} from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import { canonicalSoapSha256 } from './soap-binding';
import {
  TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
  TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
  nativeIdentityFromRendererBinding,
  rendererBindingFingerprintSha256,
} from '../note-template-docx/binding-fingerprint';
import { DOCX_MIME_TYPE } from './storage/keys';
import { parseTemplateTwinArtifactKey } from './storage/ownership';
import { validateTemplateTwin } from './validation';
import { assertTemplateTwinSourceProvenance } from './source-phi-evidence';

const SHA256 = /^[a-f0-9]{64}$/;

export const TEMPLATE_TWIN_SIGNING_VISIT_SELECT = {
  soapFinal: true,
  soapVersion: true,
  noteTemplateId: true,
  noteTemplateVersion: true,
  noteTemplate: {
    select: {
      id: true,
      version: true,
      templateKind: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          noteTemplateId: true,
          compilerVersion: true,
          irSchemaVersion: true,
          compiledDocumentIr: true,
          structureSha256: true,
          staticContentSha256: true,
          latestTestOutputObjectKey: true,
          latestTestOutputVersionId: true,
          latestTestOutputEtag: true,
          latestTestOutputSha256: true,
          certificationStatus: true,
          sourceArtifact: {
            select: {
              practiceId: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              mimeType: true,
              sizeBytes: true,
              validationStatus: true,
              privacyScanEvidence: true,
            },
          },
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
              detectionStatus: true,
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
                  approvedById: true,
                  approvedAt: true,
                },
              },
            },
          },
          certification: {
            select: {
              id: true,
              compiledStructureSha256: true,
              approvedMappingsSha256: true,
              sourcePrivacyScanEvidenceSha256: true,
              testOutputObjectKey: true,
              testOutputVersionId: true,
              testOutputEtag: true,
              testOutputSha256: true,
            },
          },
        },
      },
    },
  },
  templateTwinFill: {
    select: {
      id: true,
      practiceId: true,
      compiledVersionId: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      compilerVersion: true,
      resolverVersion: true,
      resolverModelVersion: true,
      rendererVersion: true,
      status: true,
      fillManifest: true,
      manifestVersion: true,
      manifestSha256: true,
      factSetSha256: true,
      validationResult: true,
      filledCount: true,
      needsReviewCount: true,
      notMentionedCount: true,
      conflictCount: true,
      criticalUnresolvedCount: true,
      outputObjectKey: true,
      outputVersionId: true,
      outputEtag: true,
      outputSha256: true,
      outputMimeType: true,
      outputSizeBytes: true,
      staticContentSha256: true,
      roundTripVerified: true,
      roundTripVerification: true,
      pinnedGlobalRolloutGeneration: true,
      pinnedPracticeRolloutGeneration: true,
      signedGlobalRolloutGeneration: true,
      signedPracticeRolloutGeneration: true,
      reviewedAt: true,
      reviewedById: true,
      reviewedManifestVersion: true,
      reviewedManifestSha256: true,
      signedDecisionAt: true,
      updatedAt: true,
    },
  },
} as const;

export type TemplateTwinSignBlockerCode =
  | 'TEMPLATE_PROVENANCE_UNAVAILABLE'
  | 'TENANT_MISMATCH'
  | 'TEMPLATE_VERSION_MISMATCH'
  | 'TEMPLATE_NOT_CERTIFIED'
  | 'CERTIFICATION_INTEGRITY_FAILED'
  | 'FILL_MANIFEST_MISSING'
  | 'FILL_NOT_READY'
  | 'FILL_MANIFEST_VERSION_MISMATCH'
  | 'FILL_MANIFEST_INVALID'
  | 'FILL_REVIEW_REQUIRED'
  | 'ROLLOUT_PROVENANCE_MISSING'
  | 'SOAP_BINDING_MISMATCH'
  | 'VALIDATION_FAILED'
  | 'CRITICAL_FIELDS_UNRESOLVED'
  | 'OUTPUT_MISSING'
  | 'OUTPUT_INTEGRITY_METADATA_INVALID'
  | 'ROUND_TRIP_UNVERIFIED'
  | 'STATIC_INVARIANCE_UNVERIFIED';

export interface TemplateTwinSigningContext {
  visitId: string;
  practiceId: string;
  visitStatus: string;
  soapFinal?: string | null;
  soapVersion?: number | null;
  noteTemplateId?: string | null;
  noteTemplateVersion?: number | null;
  noteTemplate?: {
    id: string;
    version: number;
    templateKind: string;
    templateTwinCompiledVersion?: {
      id: string;
      noteTemplateId: string;
      compilerVersion: string;
      irSchemaVersion: number;
      compiledDocumentIr: unknown;
      structureSha256: string;
      staticContentSha256: string;
      latestTestOutputObjectKey: string | null;
      latestTestOutputVersionId: string | null;
      latestTestOutputEtag: string | null;
      latestTestOutputSha256: string | null;
      certificationStatus: string;
      sourceArtifact: {
        practiceId: string;
        objectVersionId: string | null;
        objectEtag: string | null;
        sha256: string;
        mimeType: string;
        sizeBytes: number;
        validationStatus: string;
        privacyScanEvidence: unknown;
      };
      fields: Array<{
        fieldId: string;
        detectionStatus: string;
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
          approvedById: string | null;
          approvedAt: Date | null;
        } | null;
      }>;
      certification?: {
        id: string;
        compiledStructureSha256: string;
        approvedMappingsSha256: string;
        sourcePrivacyScanEvidenceSha256: string | null;
        testOutputObjectKey: string;
        testOutputVersionId: string | null;
        testOutputEtag: string | null;
        testOutputSha256: string;
      } | null;
    } | null;
  } | null;
  templateTwinFill?: {
    id: string;
    practiceId: string;
    compiledVersionId: string;
    noteTemplateId: string;
    noteTemplateVersion: number;
    compilerVersion: string;
    resolverVersion: string;
    resolverModelVersion: string | null;
    rendererVersion: string;
    status: string;
    fillManifest: unknown;
    manifestVersion: number;
    manifestSha256: string;
    factSetSha256: string;
    validationResult: unknown;
    filledCount: number;
    needsReviewCount: number;
    notMentionedCount: number;
    conflictCount: number;
    criticalUnresolvedCount: number;
    outputObjectKey: string | null;
    outputVersionId: string | null;
    outputEtag: string | null;
    outputSha256: string | null;
    outputMimeType: string | null;
    outputSizeBytes: number | null;
    staticContentSha256: string | null;
    roundTripVerified: boolean;
    roundTripVerification: unknown;
    pinnedGlobalRolloutGeneration: bigint | null;
    pinnedPracticeRolloutGeneration: bigint | null;
    signedGlobalRolloutGeneration: bigint | null;
    signedPracticeRolloutGeneration: bigint | null;
    reviewedAt: Date | null;
    reviewedById: string | null;
    reviewedManifestVersion: number | null;
    reviewedManifestSha256: string | null;
    signedDecisionAt: Date | null;
    updatedAt: Date;
  } | null;
}

export interface TemplateTwinManifestSignClaim {
  id: string;
  manifestVersion: number;
  manifestSha256: string;
  reviewedAt: Date;
  reviewedById: string;
  soapVersion: number;
  soapSha256: string;
  outputObjectKey: string;
  outputVersionId: string;
  outputEtag: string;
  outputSha256: string;
  outputSizeBytes: number;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
  updatedAt: Date;
}

export type TemplateTwinSigningAssessment =
  | {
      applies: false;
      ready: true;
      blockerCodes: readonly [];
      compiledVersionId: null;
      fillManifestId: null;
      claim: null;
    }
  | {
      applies: true;
      ready: boolean;
      blockerCodes: readonly TemplateTwinSignBlockerCode[];
      compiledVersionId: string | null;
      fillManifestId: string | null;
      claim: TemplateTwinManifestSignClaim | null;
    };

interface CertifiedTemplateState {
  ir: TemplateDocIR;
  mappings: SemanticMapping[];
  certifiedFieldIds: string[];
}

interface ExpectedRoundTripField {
  fieldId: string;
  partName: string;
  bindingPath: string;
  canonicalBindingPath: string;
  bindingType:
    | 'content_control'
    | 'table_cell'
    | 'legacy_form_field'
    | 'repeating_row';
  bindingOrdinal: number;
  nativeIdentity: {
    sdtId: string | null;
    tag: string | null;
    alias: string | null;
    legacyName: string | null;
  };
  sourceBindingIdentitySha256: string;
  certifiedBindingSha256: string;
  tableLocation: {
    tableIndex: number | null;
    rowIndex: number | null;
    cellIndex: number | null;
  };
  valueSha256: string;
  occurrences: number;
  disposition:
    | 'rendered'
    | 'unresolved_blank'
    | 'preserved_unresolved'
    | 'preserved_unsupported';
}

function canonicalValuesEqual(left: unknown, right: unknown): boolean {
  try {
    return canonicalSha256(left) === canonicalSha256(right);
  } catch {
    return false;
  }
}

function parseCertifiedTemplateState(
  compiled: NonNullable<
    NonNullable<TemplateTwinSigningContext['noteTemplate']>['templateTwinCompiledVersion']
  >,
): CertifiedTemplateState | null {
  const parsedIr = TemplateDocIRSchema.safeParse(compiled.compiledDocumentIr);
  if (!parsedIr.success) return null;
  const ir = parsedIr.data;

  const irFieldIds = new Set(ir.fields.map((field) => field.fieldId));
  const persistedFieldIds = new Set<string>();
  const mappings: SemanticMapping[] = [];
  const certifiedFieldIds: string[] = [];
  for (const field of compiled.fields) {
    if (
      persistedFieldIds.has(field.fieldId) ||
      !irFieldIds.has(field.fieldId) ||
      field.detectionStatus !== 'CERTIFIED' ||
      !field.mapping ||
      field.mapping.mappingStatus !== 'CERTIFIED' ||
      !field.mapping.approvedById ||
      !field.mapping.approvedAt
    ) {
      return null;
    }
    const mapping = SemanticMappingSchema.safeParse({
      fieldId: field.fieldId,
      clinicalConcept: field.mapping.clinicalConcept,
      expectedDataType: field.mapping.expectedDataType,
      polarityBehavior: field.mapping.polarityBehavior,
      temporality: field.mapping.temporality,
      laterality: field.mapping.laterality,
      unitPolicy: field.mapping.unitPolicy,
      approvedSynonyms: field.mapping.approvedSynonyms,
      required: field.mapping.required,
      blankPolicy: field.mapping.blankPolicy,
      unknownPolicy: field.mapping.unknownPolicy,
      practiceDefault: field.mapping.practiceDefault,
      status: field.mapping.mappingStatus.toLowerCase(),
    });
    if (!mapping.success || mapping.data.status !== 'certified') return null;
    persistedFieldIds.add(field.fieldId);
    mappings.push(mapping.data);
    certifiedFieldIds.push(field.fieldId);
  }
  if (
    persistedFieldIds.size !== ir.fields.length ||
    compiled.fields.length !== ir.fields.length
  ) {
    return null;
  }

  return { ir, mappings, certifiedFieldIds };
}

function certifiedCompilationIntegrity(
  compiled: NonNullable<
    NonNullable<TemplateTwinSigningContext['noteTemplate']>['templateTwinCompiledVersion']
  >,
  state: CertifiedTemplateState,
): boolean {
  const certification = compiled.certification;
  const { ir, mappings } = state;
  const recomputedStructureSha256 = canonicalSha256({
    fields: ir.fields,
    tables: ir.tables,
    nodes: ir.nodes,
    unsupported: ir.unsupported,
  });
  const recomputedStaticContentSha256 = canonicalSha256(
    ir.parts.map((part) => ({
      partName: part.partName,
      staticSha256: part.staticSha256,
    })),
  );
  let sourcePrivacyScanEvidenceSha256: string;
  try {
    sourcePrivacyScanEvidenceSha256 = assertTemplateTwinSourceProvenance({
      privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
      requireBinding: true,
      boundEvidenceSha256:
        certification?.sourcePrivacyScanEvidenceSha256,
    }).evidenceSha256;
  } catch {
    return false;
  }
  return Boolean(
    certification &&
      compiled.irSchemaVersion === ir.irSchemaVersion &&
      compiled.compilerVersion === ir.compilerVersion &&
      compiled.sourceArtifact.validationStatus === 'accepted' &&
      certification.sourcePrivacyScanEvidenceSha256 ===
        sourcePrivacyScanEvidenceSha256 &&
      compiled.sourceArtifact.sha256 === ir.source.sha256 &&
      compiled.sourceArtifact.sizeBytes === ir.source.sizeBytes &&
      compiled.sourceArtifact.mimeType === ir.source.mimeType &&
      recomputedStructureSha256 === ir.structureSha256 &&
      compiled.structureSha256 === ir.structureSha256 &&
      certification.compiledStructureSha256 === ir.structureSha256 &&
      recomputedStaticContentSha256 === ir.staticContentSha256 &&
      compiled.staticContentSha256 === ir.staticContentSha256 &&
      templateTwinMappingsSha256(mappings) ===
        certification.approvedMappingsSha256,
  );
}

function expectedRoundTripFields(
  ir: TemplateDocIR,
  resolutions: readonly FieldResolution[],
): ExpectedRoundTripField[] | null {
  if (resolutions.length !== ir.fields.length) return null;
  const byId = new Map<string, FieldResolution>();
  for (const resolution of resolutions) {
    if (byId.has(resolution.fieldId)) return null;
    byId.set(resolution.fieldId, resolution);
  }
  const expected: ExpectedRoundTripField[] = [];
  for (const field of ir.fields) {
    const resolution = byId.get(field.fieldId);
    if (!resolution) return null;
    const occurrences =
      field.rowPrototype && Array.isArray(resolution.value)
        ? resolution.value.length
        : 1;
    if (!Number.isSafeInteger(occurrences) || occurrences < 1) return null;
    const { certifiedBindingSha256, ...unsignedBinding } =
      field.rendererBinding;
    if (
      rendererBindingFingerprintSha256(field.fieldId, unsignedBinding) !==
      certifiedBindingSha256
    ) {
      return null;
    }
    expected.push({
      fieldId: field.fieldId,
      partName: field.rendererBinding.partName,
      bindingPath: field.rendererBinding.path,
      canonicalBindingPath: field.rendererBinding.canonicalPath,
      bindingType: field.rendererBinding.bindingType,
      bindingOrdinal: field.rendererBinding.ordinal,
      nativeIdentity: nativeIdentityFromRendererBinding(field.rendererBinding),
      sourceBindingIdentitySha256:
        field.rendererBinding.sourceBindingIdentitySha256,
      certifiedBindingSha256,
      tableLocation: {
        tableIndex: field.rendererBinding.tableIndex,
        rowIndex: field.rendererBinding.rowIndex,
        cellIndex: field.rendererBinding.cellIndex,
      },
      valueSha256: canonicalSha256({
        fieldId: field.fieldId,
        value: resolution.value,
      }),
      occurrences,
      disposition:
        resolution.value !== null
          ? 'rendered'
          : field.detectionStatus === 'unsupported'
            ? 'preserved_unsupported'
            : field.kind === 'checkbox' || field.rowPrototype
              ? 'preserved_unresolved'
              : 'unresolved_blank',
    });
  }
  return expected;
}

function isVerifiedRoundTrip(
  value: unknown,
  expected: {
    sourceSha256: string;
    outputSha256: string;
    fields: readonly ExpectedRoundTripField[];
  },
): boolean {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  if (!Array.isArray(row.fields) || row.fields.length !== expected.fields.length) {
    return false;
  }
  const proofByFieldId = new Map<string, Record<string, unknown>>();
  for (const candidate of row.fields) {
    if (
      !candidate ||
      typeof candidate !== 'object' ||
      Array.isArray(candidate) ||
      typeof (candidate as Record<string, unknown>).fieldId !== 'string'
    ) {
      return false;
    }
    const proof = candidate as Record<string, unknown>;
    const fieldId = proof.fieldId as string;
    if (proofByFieldId.has(fieldId)) return false;
    proofByFieldId.set(fieldId, proof);
  }
  const fieldsVerified = expected.fields.every((field) => {
    const proof = proofByFieldId.get(field.fieldId);
    const bindingEvidence = proof?.bindingEvidence;
    return Boolean(
      proof &&
        bindingEvidence &&
        typeof bindingEvidence === 'object' &&
        !Array.isArray(bindingEvidence) &&
        proof.status === 'verified' &&
        proof.partName === field.partName &&
        proof.bindingPath === field.bindingPath &&
        proof.valueSha256 === field.valueSha256 &&
        proof.occurrences === field.occurrences &&
        proof.disposition === field.disposition &&
        (bindingEvidence as Record<string, unknown>).contractVersion ===
          TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION &&
        (bindingEvidence as Record<string, unknown>).status === 'verified' &&
        (bindingEvidence as Record<string, unknown>)
          .certifiedFingerprintSha256 === field.certifiedBindingSha256 &&
        (bindingEvidence as Record<string, unknown>).outputFingerprintSha256 ===
          field.certifiedBindingSha256 &&
        (bindingEvidence as Record<string, unknown>).outputPartName ===
          field.partName &&
        (bindingEvidence as Record<string, unknown>).outputCanonicalPath ===
          field.canonicalBindingPath &&
        (bindingEvidence as Record<string, unknown>).outputBindingType ===
          field.bindingType &&
        (bindingEvidence as Record<string, unknown>).outputBindingOrdinal ===
          field.bindingOrdinal &&
        canonicalValuesEqual(
          (bindingEvidence as Record<string, unknown>).outputNativeIdentity,
          field.nativeIdentity,
        ) &&
        (bindingEvidence as Record<string, unknown>)
          .outputBindingIdentitySha256 === field.sourceBindingIdentitySha256 &&
        canonicalValuesEqual(
          (bindingEvidence as Record<string, unknown>).outputTableLocation,
          field.tableLocation,
        ),
    );
  });
  return (
    row.verificationContractVersion ===
      TEMPLATE_TWIN_READBACK_CONTRACT_VERSION &&
    row.verified === true &&
    row.packageCheck === 'verified' &&
    row.fieldCheck === 'verified' &&
    row.staticRegionCheck === 'verified' &&
    row.sourceSha256 === expected.sourceSha256 &&
    row.outputSha256 === expected.outputSha256 &&
    Number.isSafeInteger(row.untouchedEntriesVerified) &&
    Number(row.untouchedEntriesVerified) >= 0 &&
    Number.isSafeInteger(row.modifiedPartsVerified) &&
    Number(row.modifiedPartsVerified) >= 0 &&
    fieldsVerified &&
    Array.isArray(row.warningCodes) &&
    row.warningCodes.every((code) => typeof code === 'string')
  );
}

/**
 * Pure, PHI-blind signing decision. It deliberately re-validates persisted
 * JSON and cross-checks every immutable version/hash column. A UI readiness
 * flag can never authorize the READY -> SIGNED transition by itself.
 */
export function assessTemplateTwinSigning(
  context: TemplateTwinSigningContext,
): TemplateTwinSigningAssessment {
  if (!context.noteTemplateId) {
    return {
      applies: false,
      ready: true,
      blockerCodes: [],
      compiledVersionId: null,
      fillManifestId: null,
      claim: null,
    };
  }

  const template = context.noteTemplate;
  if (template?.templateKind === 'structured') {
    if (context.templateTwinFill) {
      return {
        applies: true,
        ready: false,
        blockerCodes: ['TEMPLATE_PROVENANCE_UNAVAILABLE'],
        compiledVersionId: null,
        fillManifestId: context.templateTwinFill.id,
        claim: null,
      };
    }
    return {
      applies: false,
      ready: true,
      blockerCodes: [],
      compiledVersionId: null,
      fillManifestId: null,
      claim: null,
    };
  }
  if (template?.templateKind !== 'template_twin_docx') {
    return {
      applies: true,
      ready: false,
      blockerCodes: ['TEMPLATE_PROVENANCE_UNAVAILABLE'],
      compiledVersionId: null,
      fillManifestId: context.templateTwinFill?.id ?? null,
      claim: null,
    };
  }

  const blockerCodes: TemplateTwinSignBlockerCode[] = [];
  const add = (code: TemplateTwinSignBlockerCode) => {
    if (!blockerCodes.includes(code)) blockerCodes.push(code);
  };
  const compiled = template.templateTwinCompiledVersion;
  const fill = context.templateTwinFill;
  let certifiedState: CertifiedTemplateState | null = null;
  let manifestSoapVersion: number | null = null;
  let manifestSoapSha256: string | null = null;

  if (!compiled) {
    add('TEMPLATE_PROVENANCE_UNAVAILABLE');
  } else {
    if (compiled.sourceArtifact.practiceId !== context.practiceId) {
      add('TENANT_MISMATCH');
    }
    if (
      !compiled.sourceArtifact.objectVersionId?.trim() ||
      !compiled.sourceArtifact.objectEtag?.trim()
    ) {
      add('TEMPLATE_PROVENANCE_UNAVAILABLE');
    }
    if (
      template.id !== context.noteTemplateId ||
      template.version !== context.noteTemplateVersion ||
      compiled.noteTemplateId !== context.noteTemplateId
    ) {
      add('TEMPLATE_VERSION_MISMATCH');
    }
    if (
      compiled.certificationStatus !== 'CERTIFIED' ||
      !compiled.certification
    ) {
      add('TEMPLATE_NOT_CERTIFIED');
    } else {
      certifiedState = parseCertifiedTemplateState(compiled);
      const testOutput = parseTemplateTwinArtifactKey(
        compiled.certification.testOutputObjectKey,
      );
      if (
        !certifiedState ||
        !certifiedCompilationIntegrity(compiled, certifiedState) ||
        !SHA256.test(compiled.certification.approvedMappingsSha256) ||
        !compiled.certification.testOutputVersionId?.trim() ||
        !compiled.certification.testOutputEtag?.trim() ||
        !SHA256.test(compiled.certification.testOutputSha256) ||
        compiled.certification.testOutputObjectKey !==
          compiled.latestTestOutputObjectKey ||
        compiled.certification.testOutputVersionId !==
          compiled.latestTestOutputVersionId ||
        compiled.certification.testOutputEtag !==
          compiled.latestTestOutputEtag ||
        compiled.certification.testOutputSha256 !==
          compiled.latestTestOutputSha256 ||
        testOutput?.practiceId !== context.practiceId ||
        testOutput?.kind !== 'output' ||
        testOutput?.sha256 !== compiled.certification.testOutputSha256
      ) {
        add('CERTIFICATION_INTEGRITY_FAILED');
      }
    }
  }

  if (!fill) {
    add('FILL_MANIFEST_MISSING');
  } else {
    if (
      fill.pinnedGlobalRolloutGeneration === null ||
      fill.pinnedPracticeRolloutGeneration === null ||
      (context.visitStatus === 'SIGNED' &&
        (fill.signedGlobalRolloutGeneration === null ||
          fill.signedPracticeRolloutGeneration === null ||
          fill.signedGlobalRolloutGeneration !==
            fill.pinnedGlobalRolloutGeneration ||
          fill.signedPracticeRolloutGeneration !==
            fill.pinnedPracticeRolloutGeneration))
    ) {
      add('ROLLOUT_PROVENANCE_MISSING');
    }
    if (fill.practiceId !== context.practiceId) add('TENANT_MISMATCH');
    const expectedFillStatus =
      context.visitStatus === 'SIGNED' ? 'SIGNED' : 'VERIFIED';
    if (
      fill.status !== expectedFillStatus ||
      (expectedFillStatus === 'VERIFIED' && fill.signedDecisionAt !== null) ||
      (expectedFillStatus === 'SIGNED' && fill.signedDecisionAt === null)
    ) {
      add('FILL_NOT_READY');
    }
    if (
      !fill.reviewedAt ||
      !fill.reviewedById ||
      fill.needsReviewCount !== 0 ||
      fill.conflictCount !== 0 ||
      fill.reviewedManifestVersion !== fill.manifestVersion ||
      fill.reviewedManifestSha256 !== fill.manifestSha256
    ) {
      add('FILL_REVIEW_REQUIRED');
    }
    if (
      !compiled ||
      fill.compiledVersionId !== compiled.id ||
      fill.noteTemplateId !== context.noteTemplateId ||
      fill.noteTemplateVersion !== context.noteTemplateVersion ||
      fill.compilerVersion !== compiled.compilerVersion
    ) {
      add('FILL_MANIFEST_VERSION_MISMATCH');
    }

    const parsedManifest = TemplateTwinFillManifestSchema.safeParse(
      fill.fillManifest,
    );
    const parsedValidation = TemplateTwinValidationResultSchema.safeParse(
      fill.validationResult,
    );
    if (!parsedManifest.success || !parsedValidation.success) {
      add('FILL_MANIFEST_INVALID');
    } else {
      const manifest = parsedManifest.data;
      const validation = parsedValidation.data;
      manifestSoapVersion = manifest.soapVersion;
      manifestSoapSha256 = manifest.soapSha256;
      if (
        context.soapVersion !== manifest.soapVersion ||
        typeof context.soapFinal !== 'string' ||
        canonicalSoapSha256(context.soapFinal) !== manifest.soapSha256
      ) {
        add('SOAP_BINDING_MISMATCH');
      }
      const reproducedCounts = certifiedState
        ? templateTwinCounts(manifest.fields, certifiedState.ir.fields)
        : null;
      if (
        canonicalSha256(manifest) !== fill.manifestSha256 ||
        canonicalSha256(manifest.facts) !== fill.factSetSha256 ||
        canonicalSha256(manifest.validation) !== canonicalSha256(validation) ||
        manifest.compiledVersionId !== fill.compiledVersionId ||
        manifest.noteTemplateId !== fill.noteTemplateId ||
        manifest.noteTemplateVersion !== fill.noteTemplateVersion ||
        manifest.compilerVersion !== fill.compilerVersion ||
        manifest.resolverVersion !== fill.resolverVersion ||
        manifest.resolverModelVersion !== fill.resolverModelVersion ||
        manifest.rendererVersion !== fill.rendererVersion ||
        manifest.counts.filled !== fill.filledCount ||
        manifest.counts.needsReview !== fill.needsReviewCount ||
        manifest.counts.notMentioned !== fill.notMentionedCount ||
        manifest.counts.conflicts !== fill.conflictCount ||
        manifest.counts.criticalUnresolved !== fill.criticalUnresolvedCount ||
        !reproducedCounts ||
        canonicalSha256(manifest.counts) !== canonicalSha256(reproducedCounts)
      ) {
        add('FILL_MANIFEST_VERSION_MISMATCH');
      }
      const reproducedValidation = certifiedState
        ? validateTemplateTwin({
            fields: certifiedState.ir.fields,
            mappings: certifiedState.mappings,
            facts: manifest.facts,
            resolutions: manifest.fields,
            tables: certifiedState.ir.tables,
            unsupported: certifiedState.ir.unsupported,
            certifiedFieldIds: certifiedState.certifiedFieldIds,
            now: validation.checkedAt,
          })
        : null;
      if (
        !reproducedValidation ||
        !reproducedValidation.valid ||
        reproducedValidation.issues.some(
          (issue) => issue.severity === 'blocking',
        ) ||
        canonicalSha256(reproducedValidation) !== canonicalSha256(validation)
      ) {
        add('VALIDATION_FAILED');
      }
    }

    if (fill.criticalUnresolvedCount !== 0) {
      add('CRITICAL_FIELDS_UNRESOLVED');
    }
    if (
      !fill.outputObjectKey ||
      !fill.outputVersionId?.trim() ||
      !fill.outputEtag?.trim() ||
      !fill.outputSha256 ||
      !fill.outputSizeBytes
    ) {
      add('OUTPUT_MISSING');
    } else {
      const parsedOutputKey = parseTemplateTwinArtifactKey(
        fill.outputObjectKey,
      );
      const keyParts = fill.outputObjectKey.split('/');
      if (
        !SHA256.test(fill.outputSha256) ||
        fill.outputMimeType !== DOCX_MIME_TYPE ||
        !Number.isSafeInteger(fill.outputSizeBytes) ||
        fill.outputSizeBytes < 1 ||
        parsedOutputKey?.practiceId !== context.practiceId ||
        parsedOutputKey?.kind !== 'output' ||
        parsedOutputKey?.sha256 !== fill.outputSha256 ||
        keyParts[4] !== context.visitId ||
        keyParts[5] !== fill.manifestSha256
      ) {
        add('OUTPUT_INTEGRITY_METADATA_INVALID');
      }
    }
    if (
      !compiled ||
      !fill.staticContentSha256 ||
      fill.staticContentSha256 !== compiled.staticContentSha256
    ) {
      add('STATIC_INVARIANCE_UNVERIFIED');
    }
    const roundTripFields =
      certifiedState && parsedManifest.success
        ? expectedRoundTripFields(
            certifiedState.ir,
            parsedManifest.data.fields,
          )
        : null;
    if (
      !compiled ||
      !certifiedState ||
      !fill.roundTripVerified ||
      !fill.outputSha256 ||
      !roundTripFields ||
      !isVerifiedRoundTrip(fill.roundTripVerification, {
        sourceSha256: compiled.sourceArtifact.sha256,
        outputSha256: fill.outputSha256,
        fields: roundTripFields,
      })
    ) {
      add('ROUND_TRIP_UNVERIFIED');
    }
  }

  return {
    applies: true,
    ready: blockerCodes.length === 0,
    blockerCodes,
    compiledVersionId: compiled?.id ?? null,
    fillManifestId: fill?.id ?? null,
    claim:
      blockerCodes.length === 0 &&
      fill?.outputObjectKey &&
      fill.outputVersionId &&
      fill.outputEtag &&
      fill.outputSha256 &&
      fill.outputSizeBytes &&
      fill.pinnedGlobalRolloutGeneration !== null &&
      fill.pinnedPracticeRolloutGeneration !== null &&
      manifestSoapVersion !== null &&
      manifestSoapSha256
        ? {
            id: fill.id,
            manifestVersion: fill.manifestVersion,
            manifestSha256: fill.manifestSha256,
            reviewedAt: fill.reviewedAt!,
            reviewedById: fill.reviewedById!,
            soapVersion: manifestSoapVersion,
            soapSha256: manifestSoapSha256,
            outputObjectKey: fill.outputObjectKey,
            outputVersionId: fill.outputVersionId,
            outputEtag: fill.outputEtag,
            outputSha256: fill.outputSha256,
            outputSizeBytes: fill.outputSizeBytes,
            pinnedGlobalRolloutGeneration:
              fill.pinnedGlobalRolloutGeneration,
            pinnedPracticeRolloutGeneration:
              fill.pinnedPracticeRolloutGeneration,
            updatedAt: fill.updatedAt,
          }
        : null,
  };
}
