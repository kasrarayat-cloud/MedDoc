import { canonicalSha256 } from "../template-twin/canonical";
import type { TemplateDocIR } from "../template-twin/ir";
import { TEMPLATE_TWIN_READBACK_CONTRACT_VERSION } from "./binding-fingerprint";
import {
  OFFICE_QA_EVIDENCE_CLASS,
  OFFICE_SCHEMA_QA_CONTRACT_VERSION,
  type OfficeSchemaQaResult,
} from "./office-schema-evidence";
import {
  OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
  deriveOfficeVisibleStaticFromDocxBytesQa,
  readOfficeSavedDocxFieldsQa,
  sha256OfficeDocxBytes,
  validActualManifest,
  validExpectedManifest,
  type OfficeActualFieldReadbackManifest,
  type OfficeCalculatedPresentation,
  type OfficeExpectedValueManifest,
  type OfficeByteDerivedVisibleStaticEvidence,
} from "./office-docx-byte-readback";
import { inspectDocxPackage } from "./package-security";

export {
  OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
  OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION,
  OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
  buildOfficeExpectedValueManifest,
  deriveOfficeVisibleStaticFromDocxBytesQa,
  hashOfficeQaControlState,
  hashOfficeQaSemanticValue,
  readOfficeSavedDocxFieldsQa,
  sha256OfficeDocxBytes,
} from "./office-docx-byte-readback";
export type {
  BuildOfficeExpectedValueManifestInput,
  OfficeActualFieldReadback,
  OfficeActualFieldReadbackManifest,
  OfficeCalculatedPresentation,
  OfficeCertifiedBindingExpectation,
  OfficeExpectedFieldValue,
  OfficeExpectedValueManifest,
  OfficeQaControlKind,
  OfficeByteDerivedVisibleStaticEvidence,
} from "./office-docx-byte-readback";

export const OFFICE_VISIBLE_STATIC_MANIFEST_VERSION =
  "template-twin-office-visible-static/1.0.0" as const;
export const OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION =
  "template-twin-office-visible-normalizer/1.0.0" as const;
export const OFFICE_PDF_VISUAL_METRICS_CONTRACT_VERSION =
  "template-twin-office-pdf-visual-metrics/1.0.0" as const;
export const OFFICE_PDF_PINNED_RENDERER_NAME = "Poppler pdftoppm" as const;
export const OFFICE_PDF_PINNED_RENDERER_VERSION = "25.12.0" as const;
export const OFFICE_PDF_PINNED_DPI = 144 as const;
export const OFFICE_EXECUTION_EVIDENCE_CONTRACT_VERSION =
  "template-twin-office-execution-evidence/1.0.0" as const;
export const OFFICE_PINNED_APPLICATION_NAME = "LibreOffice" as const;
export const OFFICE_PINNED_APPLICATION_VERSION =
  "LibreOffice 25.8.7.3 580(Build:3)" as const;
export const OFFICE_PINNED_IMAGE =
  "lscr.io/linuxserver/libreoffice@sha256:92b7de866a39764dc51040918885cb9178f1ec3ff11d8336621ddf2239dfcfe4" as const;
export const OFFICE_PINNED_IMAGE_DIGEST =
  "sha256:92b7de866a39764dc51040918885cb9178f1ec3ff11d8336621ddf2239dfcfe4" as const;
export const OFFICE_PACKAGE_SECURITY_QA_CONTRACT_VERSION =
  "template-twin-office-package-security-qa/1.0.0" as const;
export const OFFICE_PACKAGE_INSPECTOR_SOURCE_VERSION =
  "template-docx-package-inspector/source-v1" as const;

export type OfficeVisibleStaticRole =
  | "main_document"
  | "header"
  | "footer"
  | "styles"
  | "numbering"
  | "section_geometry";

export interface OfficeVisibleStaticRegion {
  readonly logicalRegionId: string;
  readonly role: OfficeVisibleStaticRole;
  readonly partName: string;
  readonly normalizedVisibleContentSha256: string;
  readonly normalizedStructureSha256: string;
  readonly visibleTokenCount: number;
  readonly structuralTokenCount: number;
}

export interface OfficeVisibleStaticManifest {
  readonly contractVersion: typeof OFFICE_VISIBLE_STATIC_MANIFEST_VERSION;
  readonly normalizerVersion: typeof OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION;
  readonly syntheticOnly: true;
  readonly docxSha256: string;
  readonly regions: readonly OfficeVisibleStaticRegion[];
  readonly aggregateVisibleContentSha256: string;
  readonly aggregateStructureSha256: string;
}

export interface BuildOfficeVisibleStaticManifestInput {
  readonly syntheticOnly: true;
  readonly docxSha256: string;
  readonly regions: readonly {
    readonly logicalRegionId: string;
    readonly role: OfficeVisibleStaticRole;
    readonly partName: string;
    readonly visibleTokens: readonly string[];
    readonly structuralTokens: readonly string[];
  }[];
}

export interface OfficeStructuralNormalizationRegionResult {
  readonly logicalRegionId: string;
  readonly status:
    | "normalized_equivalent"
    | "visible_content_changed"
    | "structure_changed"
    | "missing_after_office_save"
    | "unexpected_after_office_save";
  readonly sourcePartName: string | null;
  readonly outputPartName: string | null;
  readonly partNameNormalized: boolean;
  readonly visibleContentMatches: boolean;
  readonly structureMatches: boolean;
}

export interface OfficeStructuralNormalizationReport {
  readonly normalizerVersion: typeof OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION;
  readonly status: "equivalent" | "changed";
  readonly aggregateVisibleContentMatches: boolean;
  readonly aggregateStructureMatches: boolean;
  readonly partNameNormalizationCount: number;
  readonly regions: readonly OfficeStructuralNormalizationRegionResult[];
  readonly reportSha256: string;
}

export interface OfficeSecurityInspectionEvidence {
  readonly contractVersion: string;
  readonly inspectorVersion: string;
  readonly inspectedDocxSha256: string;
  readonly inspectedSizeBytes: number;
  readonly inspectionLogSha256: string;
  readonly status: "passed" | "failed";
  readonly blockerCodes: readonly string[];
  readonly externalRelationshipCount: number;
  readonly activeContentCount: number;
  readonly embeddedObjectCount: number;
  readonly packageEntryCount: number;
  readonly relationshipCount: number;
  /** Hash of every preceding field, recomputed by the verifier. */
  readonly evidenceSha256: string;
}

export type OfficeVisualDifferenceClassification =
  | "none"
  | "field_region_only_reviewed"
  | "static_region_changed"
  | "unclassified";

export interface OfficePdfPageVisualMetrics {
  readonly pageNumber: number;
  readonly originalWidthPixels: number;
  readonly originalHeightPixels: number;
  readonly roundTripWidthPixels: number;
  readonly roundTripHeightPixels: number;
  readonly originalHeaderSha256: string;
  readonly roundTripHeaderSha256: string;
  readonly originalFooterSha256: string;
  readonly roundTripFooterSha256: string;
  /** Page pixels with approved field regions masked by the QA harness. */
  readonly originalMaskedStaticSha256: string;
  readonly roundTripMaskedStaticSha256: string;
  readonly differingPixels: number;
  readonly totalPixels: number;
  readonly maximumChannelDifference: number;
  readonly approvedFieldMaskSha256: string;
  readonly approvedFieldRegionCount: number;
  readonly differenceClassification: OfficeVisualDifferenceClassification;
  readonly humanReviewed: boolean;
}

export interface OfficePdfVisualMetricsEvidence {
  readonly contractVersion: typeof OFFICE_PDF_VISUAL_METRICS_CONTRACT_VERSION;
  readonly syntheticOnly: true;
  readonly rendererName: string;
  readonly rendererVersion: string;
  readonly executionLogSha256: string;
  readonly dpi: number;
  readonly rendererOutputDocxSha256: string;
  readonly officeSavedDocxSha256: string;
  readonly originalPdfSourceDocxSha256: string;
  readonly roundTripPdfSourceDocxSha256: string;
  readonly originalPdfSha256: string;
  readonly roundTripPdfSha256: string;
  readonly originalPageCount: number;
  readonly roundTripPageCount: number;
  readonly pages: readonly OfficePdfPageVisualMetrics[];
  readonly evidenceSha256: string;
}

export type OfficeExecutionStage =
  | "version_probe"
  | "open_save_docx"
  | "export_renderer_pdf"
  | "export_office_saved_pdf";

export interface OfficeExecutionCommandEvidence {
  readonly stage: OfficeExecutionStage;
  readonly commandSha256: string;
  readonly stdoutSha256: string;
  readonly stderrSha256: string;
  readonly inputArtifactSha256: string | null;
  readonly outputArtifactSha256: string | null;
  readonly exitCode: 0;
  readonly succeeded: true;
}

/**
 * External QA attestation. Raw command logs and artifacts must be retained for
 * independent replay; this self-hashed record is never signing authority.
 */
export interface OfficeExecutionEvidence {
  readonly contractVersion: typeof OFFICE_EXECUTION_EVIDENCE_CONTRACT_VERSION;
  readonly syntheticOnly: true;
  readonly evidenceClass: typeof OFFICE_QA_EVIDENCE_CLASS;
  readonly applicationName: typeof OFFICE_PINNED_APPLICATION_NAME;
  readonly applicationVersion: typeof OFFICE_PINNED_APPLICATION_VERSION;
  readonly image: typeof OFFICE_PINNED_IMAGE;
  readonly imageDigest: typeof OFFICE_PINNED_IMAGE_DIGEST;
  readonly networkMode: "none";
  readonly sourceMountedReadOnly: true;
  readonly separateOutputPaths: true;
  readonly isolatedProfilePathSha256: string;
  readonly sourcePathSha256: string;
  readonly savedDocxPathSha256: string;
  readonly rendererPdfPathSha256: string;
  readonly officeSavedPdfPathSha256: string;
  readonly rendererOutputDocxSha256: string;
  readonly rendererOutputSizeBytes: number;
  readonly officeSavedDocxSha256: string;
  readonly officeSavedSizeBytes: number;
  readonly rendererPdfSha256: string;
  readonly officeSavedPdfSha256: string;
  readonly repairOrCorruptionDiagnosticCount: 0;
  readonly warningCount: number;
  readonly executionLogSha256: string;
  readonly commands: readonly OfficeExecutionCommandEvidence[];
  readonly evidenceSha256: string;
}

export interface PreOfficeRendererReadbackV2Evidence {
  readonly verificationContractVersion: typeof TEMPLATE_TWIN_READBACK_CONTRACT_VERSION;
  readonly status: "passed";
  readonly rendererOutputDocxSha256: string;
  readonly rendererOutputSizeBytes: number;
  readonly irStructureSha256: string;
  readonly expectedManifestSha256: string;
  readonly strictVerificationEvidenceSha256: string;
  readonly evidenceSha256: string;
}

export interface VerifyOfficeRoundTripQaInput {
  readonly syntheticOnly: true;
  readonly certifiedIr: TemplateDocIR;
  readonly expectedValues: OfficeExpectedValueManifest;
  /** Reopened to ensure the expected manifest matches actual renderer bytes. */
  readonly rendererOutputDocxBytes: Uint8Array;
  /** The only source of post-Office field evidence. */
  readonly officeSavedDocxBytes: Uint8Array;
  readonly schemaEvidence: OfficeSchemaQaResult;
  readonly officeExecutionEvidence: OfficeExecutionEvidence;
  /**
   * Externally attested raster-comparison evidence from the exact pinned
   * Poppler build. The verifier validates provenance hashes and invariants but
   * does not itself render PDFs; this evidence remains QA-only and cannot sign.
   */
  readonly visualMetrics: OfficePdfVisualMetricsEvidence;
  /** Required immutable pre-Office proof; QA cannot baseline a failed render. */
  readonly preOfficeRendererReadbackV2Evidence: PreOfficeRendererReadbackV2Evidence;
  /** Informational only: Office-saved copies are not production deliverables. */
  readonly postOfficeSavedReadbackV2Status: "passed" | "failed" | "not_run";
}

export type OfficeRoundTripQaBlockerCode =
  | "OFFICE_QA_EVIDENCE_INVALID"
  | "OFFICE_QA_OFFICE_EXECUTION_FAILED"
  | "OFFICE_QA_PRE_OFFICE_READBACK_FAILED"
  | "OFFICE_QA_FIELD_MISSING"
  | "OFFICE_QA_UNEXPECTED_FIELD"
  | "OFFICE_QA_FIELD_SEMANTICS_CHANGED"
  | "OFFICE_QA_FIELD_VALUE_CHANGED"
  | "OFFICE_QA_CONTROL_STATE_CHANGED"
  | "OFFICE_QA_OCCURRENCE_CHANGED"
  | "OFFICE_QA_BINDING_IDENTITY_LOST"
  | "OFFICE_QA_VISIBLE_STATIC_CHANGED"
  | "OFFICE_QA_STATIC_STRUCTURE_CHANGED"
  | "OFFICE_QA_SECURITY_INSPECTION_FAILED"
  | "OFFICE_QA_SCHEMA_FAILED"
  | "OFFICE_QA_PDF_PAGE_COUNT_CHANGED"
  | "OFFICE_QA_PDF_GEOMETRY_CHANGED"
  | "OFFICE_QA_PDF_HEADER_FOOTER_CHANGED"
  | "OFFICE_QA_PDF_STATIC_LAYOUT_CHANGED"
  | "OFFICE_QA_PDF_DIFFERENCE_UNREVIEWED";

export interface OfficeFieldSurvivalResult {
  readonly fieldId: string;
  readonly status: "survived" | "failed";
  readonly semanticKindMatches: boolean;
  readonly controlKindMatches: boolean;
  readonly valueMatches: boolean;
  readonly observedByteValueMatches: boolean;
  readonly officeCalculatedPresentation: OfficeCalculatedPresentation;
  readonly officeCalculatedPresentationVisuallyProven: boolean;
  readonly behaviorNormalizations: readonly string[];
  readonly controlStateMatches: boolean;
  readonly occurrenceMatches: boolean;
  readonly logicalBindingIdentityMatches: boolean;
  readonly certifiedPartPathTypeOrdinalMatches: boolean;
  readonly pathNormalizationObserved: boolean;
  readonly serializationNormalized: boolean;
  readonly rendererControlSerializationSha256: string;
  readonly outputControlSerializationSha256: string | null;
  readonly rendererObservedValueSha256: string;
  readonly outputObservedValueSha256: string | null;
}

export interface OfficeRoundTripQaGateResult {
  readonly status: "passed" | "failed" | "external_tool_pending_word";
  readonly blockerCodes: readonly OfficeRoundTripQaBlockerCode[];
}

/**
 * QA-only Office compatibility result. It intentionally has no `verified`,
 * `verificationContractVersion`, `packageCheck`, `fieldCheck`, or
 * `staticRegionCheck` members used by production signing readback v2.
 */
export interface OfficeRoundTripQaResult {
  readonly evidenceClass: typeof OFFICE_QA_EVIDENCE_CLASS;
  readonly contractVersion: typeof OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION;
  readonly qaOnly: true;
  readonly signingEligible: false;
  readonly productionStateTransitionEligible: false;
  readonly mayReplaceProductionReadbackV2: false;
  readonly mayAuthorizeSigning: false;
  readonly mayAuthorizeExportOrDownload: false;
  readonly status: "passed" | "failed" | "external_tool_pending_word";
  /** Allows more synthetic compatibility work; never means Office approval. */
  readonly compatibilityEngineeringEligible: boolean;
  readonly officeCompatibilityApproved: false;
  readonly desktopWordApprovalStatus: "pending";
  readonly blockerCodes: readonly OfficeRoundTripQaBlockerCode[];
  readonly gates: {
    readonly fields: OfficeRoundTripQaGateResult;
    readonly visibleStatic: OfficeRoundTripQaGateResult;
    readonly security: OfficeRoundTripQaGateResult;
    readonly schema: OfficeRoundTripQaGateResult;
    readonly visual: OfficeRoundTripQaGateResult;
  };
  readonly fields: readonly OfficeFieldSurvivalResult[];
  readonly rendererBaselineReadbackManifestSha256: string | null;
  readonly officeSavedReadbackManifestSha256: string | null;
  readonly rendererVisibleStaticEvidenceSha256: string | null;
  readonly officeSavedVisibleStaticEvidenceSha256: string | null;
  readonly securityInspectionEvidenceSha256: string;
  readonly officeExecutionEvidenceSha256: string | null;
  readonly structuralNormalizationReport: OfficeStructuralNormalizationReport;
  readonly schemaEvidenceMatrixSha256: string;
  readonly readbackV2Boundary: {
    readonly preOfficeRendererStatus: "passed";
    readonly preOfficeRendererEvidenceSha256: string;
    readonly postOfficeSavedObservedStatus: VerifyOfficeRoundTripQaInput["postOfficeSavedReadbackV2Status"];
    readonly qaResultDoesNotChangeProductionStatus: true;
  };
  readonly resultSha256: string;
}

const SHA256 = /^[a-f0-9]{64}$/;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,239}$/;
const VISUAL_DIFFERENCE_CLASSIFICATIONS =
  new Set<OfficeVisualDifferenceClassification>([
    "none",
    "field_region_only_reviewed",
    "static_region_changed",
    "unclassified",
  ]);
function uniqueSorted<T extends string>(values: readonly T[]): T[] {
  return [...new Set(values)].sort() as T[];
}

function validId(value: string): boolean {
  return SAFE_ID.test(value);
}

function validCount(value: number, minimum = 0): boolean {
  return Number.isSafeInteger(value) && value >= minimum;
}

export function normalizeOfficeVisibleStaticText(value: string): string {
  return value
    .normalize("NFC")
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n")
    .replace(/[\t\f\v ]+/g, " ")
    .replace(/ *\n */g, "\n")
    .trim();
}

export function buildOfficeVisibleStaticManifest(
  input: BuildOfficeVisibleStaticManifestInput,
): OfficeVisibleStaticManifest {
  if (
    input.syntheticOnly !== true ||
    !SHA256.test(input.docxSha256) ||
    input.regions.length === 0 ||
    new Set(input.regions.map((region) => region.logicalRegionId)).size !==
      input.regions.length
  ) {
    throw new Error("Invalid QA-only visible-static manifest input.");
  }
  const regions = input.regions.map((region) => {
    if (
      !validId(region.logicalRegionId) ||
      region.partName.length < 1 ||
      region.partName.length > 240
    ) {
      throw new Error("Invalid QA-only visible-static region.");
    }
    const visibleTokens = region.visibleTokens.map(
      normalizeOfficeVisibleStaticText,
    );
    const structuralTokens = region.structuralTokens.map(
      normalizeOfficeVisibleStaticText,
    );
    return Object.freeze({
      logicalRegionId: region.logicalRegionId,
      role: region.role,
      partName: region.partName,
      normalizedVisibleContentSha256: canonicalSha256(visibleTokens),
      normalizedStructureSha256: canonicalSha256(structuralTokens),
      visibleTokenCount: visibleTokens.length,
      structuralTokenCount: structuralTokens.length,
    });
  });
  regions.sort((left, right) =>
    left.logicalRegionId.localeCompare(right.logicalRegionId),
  );
  return Object.freeze({
    contractVersion: OFFICE_VISIBLE_STATIC_MANIFEST_VERSION,
    normalizerVersion: OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION,
    syntheticOnly: true,
    docxSha256: input.docxSha256,
    regions: Object.freeze(regions),
    aggregateVisibleContentSha256: canonicalSha256(
      regions.map((region) => ({
        logicalRegionId: region.logicalRegionId,
        role: region.role,
        sha256: region.normalizedVisibleContentSha256,
        count: region.visibleTokenCount,
      })),
    ),
    aggregateStructureSha256: canonicalSha256(
      regions.map((region) => ({
        logicalRegionId: region.logicalRegionId,
        role: region.role,
        sha256: region.normalizedStructureSha256,
        count: region.structuralTokenCount,
      })),
    ),
  });
}

export function buildOfficeVisibleStaticManifestFromDocxBytes(input: {
  readonly syntheticOnly: true;
  readonly docxBytes: Uint8Array;
  readonly expected: OfficeExpectedValueManifest;
}): {
  readonly manifest: OfficeVisibleStaticManifest;
  readonly byteEvidence: OfficeByteDerivedVisibleStaticEvidence;
} {
  const byteEvidence = deriveOfficeVisibleStaticFromDocxBytesQa(input);
  const { evidenceSha256, ...unsigned } = byteEvidence;
  if (evidenceSha256 !== canonicalSha256(unsigned)) {
    throw new Error("Invalid byte-derived Office static evidence.");
  }
  return Object.freeze({
    manifest: buildOfficeVisibleStaticManifest({
      syntheticOnly: true,
      docxSha256: byteEvidence.docxSha256,
      regions: byteEvidence.regions,
    }),
    byteEvidence,
  });
}

export function compareOfficeVisibleStaticManifests(
  source: OfficeVisibleStaticManifest,
  output: OfficeVisibleStaticManifest,
): OfficeStructuralNormalizationReport {
  const sourceRegions = new Map(
    source.regions.map((region) => [region.logicalRegionId, region]),
  );
  const outputRegions = new Map(
    output.regions.map((region) => [region.logicalRegionId, region]),
  );
  const regionIds = uniqueSorted([
    ...sourceRegions.keys(),
    ...outputRegions.keys(),
  ]);
  const regions: OfficeStructuralNormalizationRegionResult[] = regionIds.map(
    (logicalRegionId) => {
      const before = sourceRegions.get(logicalRegionId);
      const after = outputRegions.get(logicalRegionId);
      if (!before) {
        return Object.freeze({
          logicalRegionId,
          status: "unexpected_after_office_save" as const,
          sourcePartName: null,
          outputPartName: after?.partName ?? null,
          partNameNormalized: false,
          visibleContentMatches: false,
          structureMatches: false,
        });
      }
      if (!after) {
        return Object.freeze({
          logicalRegionId,
          status: "missing_after_office_save" as const,
          sourcePartName: before.partName,
          outputPartName: null,
          partNameNormalized: false,
          visibleContentMatches: false,
          structureMatches: false,
        });
      }
      const visibleContentMatches =
        before.role === after.role &&
        before.normalizedVisibleContentSha256 ===
          after.normalizedVisibleContentSha256 &&
        before.visibleTokenCount === after.visibleTokenCount;
      const structureMatches =
        before.role === after.role &&
        before.normalizedStructureSha256 === after.normalizedStructureSha256 &&
        before.structuralTokenCount === after.structuralTokenCount;
      return Object.freeze({
        logicalRegionId,
        status: !visibleContentMatches
          ? ("visible_content_changed" as const)
          : !structureMatches
            ? ("structure_changed" as const)
            : ("normalized_equivalent" as const),
        sourcePartName: before.partName,
        outputPartName: after.partName,
        partNameNormalized: before.partName !== after.partName,
        visibleContentMatches,
        structureMatches,
      });
    },
  );
  const aggregateVisibleContentMatches = regions.every(
    (region) => region.visibleContentMatches,
  );
  const aggregateStructureMatches = regions.every(
    (region) => region.structureMatches,
  );
  const reportWithoutHash = {
    normalizerVersion: OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION,
    status:
      aggregateVisibleContentMatches && aggregateStructureMatches
        ? ("equivalent" as const)
        : ("changed" as const),
    aggregateVisibleContentMatches,
    aggregateStructureMatches,
    partNameNormalizationCount: regions.filter(
      (region) => region.partNameNormalized,
    ).length,
    regions,
  };
  return Object.freeze({
    ...reportWithoutHash,
    reportSha256: canonicalSha256(reportWithoutHash),
  });
}

function unavailableStructuralNormalizationReport(): OfficeStructuralNormalizationReport {
  const unsigned = {
    normalizerVersion: OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION,
    status: "changed" as const,
    aggregateVisibleContentMatches: false,
    aggregateStructureMatches: false,
    partNameNormalizationCount: 0,
    regions: Object.freeze(
      [],
    ) as readonly OfficeStructuralNormalizationRegionResult[],
  };
  return Object.freeze({
    ...unsigned,
    reportSha256: canonicalSha256(unsigned),
  });
}

function validVisibleStaticManifest(
  manifest: OfficeVisibleStaticManifest,
): boolean {
  const sortedRegions = [...manifest.regions].sort((left, right) =>
    left.logicalRegionId.localeCompare(right.logicalRegionId),
  );
  const expectedVisibleAggregate = canonicalSha256(
    sortedRegions.map((region) => ({
      logicalRegionId: region.logicalRegionId,
      role: region.role,
      sha256: region.normalizedVisibleContentSha256,
      count: region.visibleTokenCount,
    })),
  );
  const expectedStructureAggregate = canonicalSha256(
    sortedRegions.map((region) => ({
      logicalRegionId: region.logicalRegionId,
      role: region.role,
      sha256: region.normalizedStructureSha256,
      count: region.structuralTokenCount,
    })),
  );
  return Boolean(
    manifest.contractVersion === OFFICE_VISIBLE_STATIC_MANIFEST_VERSION &&
    manifest.normalizerVersion === OFFICE_VISIBLE_STATIC_NORMALIZER_VERSION &&
    manifest.syntheticOnly === true &&
    SHA256.test(manifest.docxSha256) &&
    SHA256.test(manifest.aggregateVisibleContentSha256) &&
    SHA256.test(manifest.aggregateStructureSha256) &&
    manifest.aggregateVisibleContentSha256 === expectedVisibleAggregate &&
    manifest.aggregateStructureSha256 === expectedStructureAggregate &&
    manifest.regions.length > 0 &&
    new Set(manifest.regions.map((region) => region.logicalRegionId)).size ===
      manifest.regions.length &&
    manifest.regions.every(
      (region) =>
        validId(region.logicalRegionId) &&
        region.partName.length > 0 &&
        region.partName.length <= 240 &&
        SHA256.test(region.normalizedVisibleContentSha256) &&
        SHA256.test(region.normalizedStructureSha256) &&
        validCount(region.visibleTokenCount) &&
        validCount(region.structuralTokenCount),
    ),
  );
}

function validVisualMetrics(metrics: OfficePdfVisualMetricsEvidence): boolean {
  const { evidenceSha256, ...unsigned } = metrics;
  const pageNumbers = [...metrics.pages]
    .map((page) => page.pageNumber)
    .sort((left, right) => left - right);
  return Boolean(
    metrics.contractVersion === OFFICE_PDF_VISUAL_METRICS_CONTRACT_VERSION &&
    metrics.syntheticOnly === true &&
    metrics.rendererName === OFFICE_PDF_PINNED_RENDERER_NAME &&
    metrics.rendererVersion === OFFICE_PDF_PINNED_RENDERER_VERSION &&
    SHA256.test(metrics.executionLogSha256) &&
    metrics.dpi === OFFICE_PDF_PINNED_DPI &&
    SHA256.test(metrics.rendererOutputDocxSha256) &&
    SHA256.test(metrics.officeSavedDocxSha256) &&
    SHA256.test(metrics.originalPdfSourceDocxSha256) &&
    SHA256.test(metrics.roundTripPdfSourceDocxSha256) &&
    SHA256.test(metrics.originalPdfSha256) &&
    SHA256.test(metrics.roundTripPdfSha256) &&
    validCount(metrics.originalPageCount, 1) &&
    validCount(metrics.roundTripPageCount, 1) &&
    metrics.pages.length === metrics.originalPageCount &&
    metrics.pages.length === metrics.roundTripPageCount &&
    pageNumbers.every((pageNumber, index) => pageNumber === index + 1) &&
    new Set(metrics.pages.map((page) => page.pageNumber)).size ===
      metrics.pages.length &&
    metrics.pages.every(
      (page) =>
        validCount(page.pageNumber, 1) &&
        validCount(page.originalWidthPixels, 1) &&
        validCount(page.originalHeightPixels, 1) &&
        validCount(page.roundTripWidthPixels, 1) &&
        validCount(page.roundTripHeightPixels, 1) &&
        SHA256.test(page.originalHeaderSha256) &&
        SHA256.test(page.roundTripHeaderSha256) &&
        SHA256.test(page.originalFooterSha256) &&
        SHA256.test(page.roundTripFooterSha256) &&
        SHA256.test(page.originalMaskedStaticSha256) &&
        SHA256.test(page.roundTripMaskedStaticSha256) &&
        validCount(page.differingPixels) &&
        validCount(page.totalPixels, 1) &&
        page.differingPixels <= page.totalPixels &&
        validCount(page.maximumChannelDifference) &&
        page.maximumChannelDifference <= 255 &&
        SHA256.test(page.approvedFieldMaskSha256) &&
        validCount(page.approvedFieldRegionCount) &&
        VISUAL_DIFFERENCE_CLASSIFICATIONS.has(page.differenceClassification) &&
        (page.differenceClassification !== "field_region_only_reviewed" ||
          (page.approvedFieldRegionCount > 0 && page.humanReviewed)) &&
        (page.differenceClassification !== "none" ||
          (page.approvedFieldRegionCount === 0 && page.differingPixels === 0)),
    ) &&
    SHA256.test(evidenceSha256) &&
    evidenceSha256 === canonicalSha256(unsigned),
  );
}

function visualMetricsProveExactFullDocumentSurvival(
  metrics: OfficePdfVisualMetricsEvidence,
  rendererOutputDocxSha256: string,
  officeSavedDocxSha256: string,
): boolean {
  return Boolean(
    validVisualMetrics(metrics) &&
    metrics.rendererOutputDocxSha256 === rendererOutputDocxSha256 &&
    metrics.officeSavedDocxSha256 === officeSavedDocxSha256 &&
    metrics.originalPdfSourceDocxSha256 === rendererOutputDocxSha256 &&
    metrics.roundTripPdfSourceDocxSha256 === officeSavedDocxSha256 &&
    metrics.originalPageCount === metrics.roundTripPageCount &&
    metrics.pages.every(
      (page) =>
        page.originalWidthPixels === page.roundTripWidthPixels &&
        page.originalHeightPixels === page.roundTripHeightPixels &&
        page.originalHeaderSha256 === page.roundTripHeaderSha256 &&
        page.originalFooterSha256 === page.roundTripFooterSha256 &&
        page.originalMaskedStaticSha256 === page.roundTripMaskedStaticSha256 &&
        page.differingPixels === 0 &&
        page.maximumChannelDifference === 0 &&
        page.approvedFieldRegionCount === 0 &&
        page.differenceClassification === "none",
    ),
  );
}

export function hashOfficeSecurityInspectionEvidence(
  evidence: Omit<OfficeSecurityInspectionEvidence, "evidenceSha256">,
): string {
  return canonicalSha256(evidence);
}

/**
 * Derives package-security evidence directly from the Office-saved bytes.
 * Callers cannot submit a precomputed "pass": the same bytes used by field
 * readback are independently reopened by the production package inspector.
 */
export function inspectOfficeDocxSecurityQa(
  officeSavedDocxBytes: Uint8Array,
): OfficeSecurityInspectionEvidence {
  const inspectedDocxSha256 = sha256OfficeDocxBytes(officeSavedDocxBytes);
  const inspectedSizeBytes = officeSavedDocxBytes.byteLength;
  try {
    const inspected = inspectDocxPackage(officeSavedDocxBytes);
    const inspectionSummary = {
      inspectedDocxSha256,
      inspectedSizeBytes,
      packageEntryCount: inspected.zip.entries.size,
      relationshipCount: inspected.relationships.length,
      contentTypeCount: inspected.contentTypes.size,
      mainPartName: inspected.mainPartName,
      headerPartCount: inspected.headerPartNames.length,
      footerPartCount: inspected.footerPartNames.length,
    };
    const unsigned = {
      contractVersion: OFFICE_PACKAGE_SECURITY_QA_CONTRACT_VERSION,
      inspectorVersion: OFFICE_PACKAGE_INSPECTOR_SOURCE_VERSION,
      inspectedDocxSha256,
      inspectedSizeBytes,
      inspectionLogSha256: canonicalSha256(inspectionSummary),
      status: "passed" as const,
      blockerCodes: Object.freeze([] as string[]),
      externalRelationshipCount: 0,
      activeContentCount: 0,
      embeddedObjectCount: 0,
      packageEntryCount: inspected.zip.entries.size,
      relationshipCount: inspected.relationships.length,
    };
    return Object.freeze({
      ...unsigned,
      evidenceSha256: hashOfficeSecurityInspectionEvidence(unsigned),
    });
  } catch {
    const blockerCodes = Object.freeze(["PACKAGE_INSPECTION_REJECTED"]);
    const unsigned = {
      contractVersion: OFFICE_PACKAGE_SECURITY_QA_CONTRACT_VERSION,
      inspectorVersion: OFFICE_PACKAGE_INSPECTOR_SOURCE_VERSION,
      inspectedDocxSha256,
      inspectedSizeBytes,
      inspectionLogSha256: canonicalSha256({
        inspectedDocxSha256,
        inspectedSizeBytes,
        status: "failed",
        blockerCodes,
      }),
      status: "failed" as const,
      blockerCodes,
      externalRelationshipCount: 0,
      activeContentCount: 0,
      embeddedObjectCount: 0,
      packageEntryCount: 0,
      relationshipCount: 0,
    };
    return Object.freeze({
      ...unsigned,
      evidenceSha256: hashOfficeSecurityInspectionEvidence(unsigned),
    });
  }
}

export function hashOfficePdfVisualMetricsEvidence(
  evidence: Omit<OfficePdfVisualMetricsEvidence, "evidenceSha256">,
): string {
  return canonicalSha256(evidence);
}

export function hashOfficeExecutionEvidence(
  evidence: Omit<OfficeExecutionEvidence, "evidenceSha256">,
): string {
  return canonicalSha256(evidence);
}

export function hashPreOfficeRendererReadbackV2Evidence(
  evidence: Omit<PreOfficeRendererReadbackV2Evidence, "evidenceSha256">,
): string {
  return canonicalSha256(evidence);
}

function validAttestedSha256(value: string): boolean {
  return SHA256.test(value) && !/^0{64}$/.test(value);
}

function validOfficeExecutionEvidence(
  evidence: OfficeExecutionEvidence | undefined,
  expected: OfficeExpectedValueManifest,
  actual: OfficeActualFieldReadbackManifest | null,
  visual: OfficePdfVisualMetricsEvidence,
): boolean {
  if (!evidence || !actual) return false;
  const { evidenceSha256, ...unsigned } = evidence;
  const stages: readonly OfficeExecutionStage[] = [
    "version_probe",
    "open_save_docx",
    "export_renderer_pdf",
    "export_office_saved_pdf",
  ];
  const byStage = new Map(
    evidence.commands.map((command) => [command.stage, command]),
  );
  const paths = [
    evidence.isolatedProfilePathSha256,
    evidence.sourcePathSha256,
    evidence.savedDocxPathSha256,
    evidence.rendererPdfPathSha256,
    evidence.officeSavedPdfPathSha256,
  ];
  const commandHashes = evidence.commands.map(
    (command) => command.commandSha256,
  );
  const command = (stage: OfficeExecutionStage) => byStage.get(stage);
  return Boolean(
    evidence.contractVersion === OFFICE_EXECUTION_EVIDENCE_CONTRACT_VERSION &&
    evidence.syntheticOnly === true &&
    evidence.evidenceClass === OFFICE_QA_EVIDENCE_CLASS &&
    evidence.applicationName === OFFICE_PINNED_APPLICATION_NAME &&
    evidence.applicationVersion === OFFICE_PINNED_APPLICATION_VERSION &&
    evidence.image === OFFICE_PINNED_IMAGE &&
    evidence.imageDigest === OFFICE_PINNED_IMAGE_DIGEST &&
    evidence.networkMode === "none" &&
    evidence.sourceMountedReadOnly === true &&
    evidence.separateOutputPaths === true &&
    paths.every(validAttestedSha256) &&
    new Set(paths).size === paths.length &&
    evidence.rendererOutputDocxSha256 === expected.rendererOutputDocxSha256 &&
    evidence.rendererOutputSizeBytes === expected.rendererOutputSizeBytes &&
    evidence.officeSavedDocxSha256 === actual.officeSavedDocxSha256 &&
    evidence.officeSavedSizeBytes === actual.officeSavedSizeBytes &&
    evidence.rendererOutputDocxSha256 !== evidence.officeSavedDocxSha256 &&
    evidence.rendererPdfSha256 === visual.originalPdfSha256 &&
    evidence.officeSavedPdfSha256 === visual.roundTripPdfSha256 &&
    evidence.repairOrCorruptionDiagnosticCount === 0 &&
    validCount(evidence.warningCount) &&
    validAttestedSha256(evidence.executionLogSha256) &&
    evidence.commands.length === stages.length &&
    byStage.size === stages.length &&
    stages.every((stage) => byStage.has(stage)) &&
    commandHashes.every(validAttestedSha256) &&
    new Set(commandHashes).size === commandHashes.length &&
    evidence.commands.every(
      (candidate) =>
        candidate.succeeded === true &&
        candidate.exitCode === 0 &&
        validAttestedSha256(candidate.stdoutSha256) &&
        validAttestedSha256(candidate.stderrSha256),
    ) &&
    command("version_probe")?.inputArtifactSha256 === null &&
    command("version_probe")?.outputArtifactSha256 === null &&
    command("open_save_docx")?.inputArtifactSha256 ===
      expected.rendererOutputDocxSha256 &&
    command("open_save_docx")?.outputArtifactSha256 ===
      actual.officeSavedDocxSha256 &&
    command("export_renderer_pdf")?.inputArtifactSha256 ===
      expected.rendererOutputDocxSha256 &&
    command("export_renderer_pdf")?.outputArtifactSha256 ===
      visual.originalPdfSha256 &&
    command("export_office_saved_pdf")?.inputArtifactSha256 ===
      actual.officeSavedDocxSha256 &&
    command("export_office_saved_pdf")?.outputArtifactSha256 ===
      visual.roundTripPdfSha256 &&
    validAttestedSha256(evidenceSha256) &&
    evidenceSha256 === hashOfficeExecutionEvidence(unsigned),
  );
}

function validPreOfficeRendererReadbackV2Evidence(
  evidence: PreOfficeRendererReadbackV2Evidence | undefined,
  expected: OfficeExpectedValueManifest,
  ir: TemplateDocIR,
): boolean {
  if (!evidence) return false;
  const { evidenceSha256, ...unsigned } = evidence;
  return Boolean(
    evidence.verificationContractVersion ===
      TEMPLATE_TWIN_READBACK_CONTRACT_VERSION &&
    evidence.status === "passed" &&
    evidence.rendererOutputDocxSha256 === expected.rendererOutputDocxSha256 &&
    evidence.rendererOutputSizeBytes === expected.rendererOutputSizeBytes &&
    evidence.irStructureSha256 === ir.structureSha256 &&
    evidence.expectedManifestSha256 === expected.manifestSha256 &&
    validAttestedSha256(evidence.strictVerificationEvidenceSha256) &&
    validAttestedSha256(evidenceSha256) &&
    evidenceSha256 === hashPreOfficeRendererReadbackV2Evidence(unsigned),
  );
}

function expectedManifestMatchesCertifiedIr(
  expected: OfficeExpectedValueManifest,
  ir: TemplateDocIR,
): boolean {
  const fieldsById = new Map(ir.fields.map((field) => [field.fieldId, field]));
  if (
    expected.sourceDocxSha256 !== ir.source.sha256 ||
    expected.irStructureSha256 !== ir.structureSha256 ||
    expected.expectedIrFieldCount !== ir.fields.length ||
    expected.irFieldIdsSha256 !== canonicalSha256([...fieldsById.keys()].sort())
  ) {
    return false;
  }
  return expected.fields.every((candidate) => {
    const field = fieldsById.get(candidate.fieldId);
    if (!field) return false;
    const binding = field.rendererBinding;
    return Boolean(
      candidate.semanticKind === field.kind &&
      candidate.certifiedBinding.partName === binding.partName &&
      candidate.certifiedBinding.canonicalPath === binding.canonicalPath &&
      candidate.certifiedBinding.bindingType === binding.bindingType &&
      candidate.certifiedBinding.ordinal === binding.ordinal &&
      canonicalSha256(candidate.certifiedBinding.nativeIdentity) ===
        canonicalSha256({
          sdtId: binding.sdtId,
          tag: binding.tag,
          alias: binding.alias,
          legacyName: binding.legacyName,
        }) &&
      candidate.certifiedBinding.sourceControlSha256 ===
        binding.sourceControlSha256 &&
      candidate.certifiedBinding.sourceBindingIdentitySha256 ===
        binding.sourceBindingIdentitySha256 &&
      candidate.certifiedBinding.certifiedBindingSha256 ===
        binding.certifiedBindingSha256 &&
      candidate.certifiedBinding.canonicalRepeatAncestorPath ===
        binding.canonicalRepeatAncestorPath &&
      canonicalSha256(candidate.certifiedBinding.tableLocation) ===
        canonicalSha256({
          tableIndex: binding.tableIndex,
          rowIndex: binding.rowIndex,
          cellIndex: binding.cellIndex,
        }) &&
      candidate.certifiedBinding.labelContextSha256 ===
        canonicalSha256(field.originalLabel),
    );
  });
}

function rendererBaselineMatchesExpected(
  baseline: OfficeActualFieldReadbackManifest,
  expected: OfficeExpectedValueManifest,
): boolean {
  if (
    baseline.officeSavedDocxSha256 !== expected.rendererOutputDocxSha256 ||
    baseline.officeSavedSizeBytes !== expected.rendererOutputSizeBytes ||
    baseline.unexpectedBindingCount !== 0 ||
    baseline.ambiguousBindingCount !== 0
  ) {
    return false;
  }
  const byId = new Map(baseline.fields.map((field) => [field.fieldId, field]));
  return expected.fields.every((candidate) => {
    const actual = byId.get(candidate.fieldId);
    return Boolean(
      actual &&
      actual.semanticKind === candidate.semanticKind &&
      actual.controlKind === candidate.controlKind &&
      actual.actualValueSha256 === candidate.expectedValueSha256 &&
      actual.outputObservedValueSha256 ===
        candidate.rendererObservedValueSha256 &&
      actual.actualControlStateSha256 ===
        candidate.expectedControlStateSha256 &&
      actual.outputControlSerializationSha256 ===
        candidate.rendererControlSerializationSha256 &&
      actual.officeCalculatedPresentation === "none" &&
      actual.actualOccurrences === candidate.expectedOccurrences &&
      actual.actualDisposition === candidate.expectedDisposition &&
      actual.outputBinding.partName === candidate.certifiedBinding.partName &&
      actual.outputBinding.canonicalPath ===
        candidate.certifiedBinding.canonicalPath &&
      actual.outputBinding.bindingType ===
        candidate.certifiedBinding.bindingType &&
      actual.outputBinding.ordinal === candidate.certifiedBinding.ordinal &&
      actual.outputBinding.logicalFieldLocatorSha256 ===
        candidate.certifiedBinding.logicalFieldLocatorSha256 &&
      actual.outputBinding.outputBindingIdentitySha256 ===
        candidate.certifiedBinding.sourceBindingIdentitySha256 &&
      canonicalSha256(actual.outputBinding.tableLocation) ===
        canonicalSha256(candidate.certifiedBinding.tableLocation),
    );
  });
}

function securityEvidenceHashMatches(
  evidence: OfficeSecurityInspectionEvidence,
): boolean {
  const { evidenceSha256, ...unsigned } = evidence;
  return (
    SHA256.test(evidenceSha256) &&
    evidenceSha256 === hashOfficeSecurityInspectionEvidence(unsigned)
  );
}

function schemaMatrixIsInternallyConsistent(
  schema: OfficeSchemaQaResult,
): boolean {
  if (
    schema.blockerCodes.length !== 0 ||
    schema.compatibilityEngineeringEligible !== true ||
    !SHA256.test(schema.reviewerProvenanceSha256) ||
    schema.matrixSha256 !== canonicalSha256(schema.matrix) ||
    new Set(schema.matrix.map((row) => row.matrixId)).size !==
      schema.matrix.length
  ) {
    return false;
  }
  for (const row of schema.matrix) {
    const { matrixId, ...withoutId } = row;
    if (
      matrixId !== `office_schema_${canonicalSha256(withoutId).slice(0, 24)}` ||
      row.blocksQaGate ||
      (row.severity === "error" &&
        (!row.requiresDesktopWordResolution ||
          row.disposition !== "external_tool_pending_word" ||
          row.stage !== "office_saved")) ||
      (row.severity === "warning" &&
        (row.requiresDesktopWordResolution ||
          row.disposition !== "reviewed_non_blocking"))
    ) {
      return false;
    }
  }
  for (const stage of schema.stages) {
    const rows = schema.matrix.filter(
      (row) =>
        row.stage === stage.stage && row.targetFormat === stage.targetFormat,
    );
    const errors = rows.filter((row) => row.severity === "error");
    const warnings = rows.filter((row) => row.severity === "warning");
    const pendingWordErrors = errors.filter(
      (row) => row.requiresDesktopWordResolution,
    );
    const artifact = stage.artifactEvidence[0];
    if (
      stage.openedArtifactCount !== 1 ||
      stage.diagnosticCount !== rows.length ||
      stage.errorCount !== errors.length ||
      stage.warningCount !== warnings.length ||
      stage.reviewedNonBlockingWarningCount !== warnings.length ||
      stage.externalToolPendingWordErrorCount !== pendingWordErrors.length ||
      !artifact ||
      rows.some(
        (row) =>
          row.artifactId !== artifact.artifactId ||
          row.artifactSha256 !== artifact.artifactSha256,
      ) ||
      rows
        .map((row) => row.diagnosticIndex)
        .sort((left, right) => left - right)
        .some((diagnosticIndex, index) => diagnosticIndex !== index) ||
      (stage.stage !== "office_saved" && pendingWordErrors.length > 0) ||
      stage.status !==
        (pendingWordErrors.length > 0 ? "external_tool_pending_word" : "passed")
    ) {
      return false;
    }
  }
  const expectedStatus = schema.stages.some(
    (stage) => stage.status === "external_tool_pending_word",
  )
    ? "external_tool_pending_word"
    : "passed";
  return schema.status === expectedStatus;
}

function schemaEvidenceHashesMatch(
  schema: OfficeSchemaQaResult,
  expected: OfficeExpectedValueManifest,
  actual: OfficeActualFieldReadbackManifest | null,
): boolean {
  const { evidenceSha256, ...unsigned } = schema;
  if (
    !actual ||
    !SHA256.test(evidenceSha256) ||
    evidenceSha256 !== canonicalSha256(unsigned) ||
    !schemaMatrixIsInternallyConsistent(schema)
  ) {
    return false;
  }
  const expectedByStage = [
    ["source", expected.sourceDocxSha256],
    ["renderer_output", expected.rendererOutputDocxSha256],
    ["office_saved", actual.officeSavedDocxSha256],
  ] as const;
  const expectedStageKeys = new Set(
    expectedByStage.flatMap(([stage]) => [
      `${stage}\u0000Office2013`,
      `${stage}\u0000Microsoft365`,
    ]),
  );
  const observedStageKeys = new Set(
    schema.stages.map((stage) => `${stage.stage}\u0000${stage.targetFormat}`),
  );
  return Boolean(
    schema.stages.length === expectedStageKeys.size &&
    observedStageKeys.size === expectedStageKeys.size &&
    [...expectedStageKeys].every((key) => observedStageKeys.has(key)) &&
    expectedByStage.every(([stageName, artifactSha256]) =>
      ["Office2013", "Microsoft365"].every((targetFormat) =>
        schema.stages
          .filter(
            (stage) =>
              stage.stage === stageName && stage.targetFormat === targetFormat,
          )
          .some(
            (stage) =>
              stage.validatorName ===
                "DocumentFormat.OpenXml.OpenXmlValidator" &&
              stage.validatorVersion === "3.5.1.0" &&
              stage.executionLogSha256 !== null &&
              SHA256.test(stage.executionLogSha256) &&
              (stageName === "office_saved"
                ? ["passed", "external_tool_pending_word"].includes(
                    stage.status,
                  )
                : stage.status === "passed") &&
              stage.requiredArtifactIds.length === 1 &&
              stage.observedArtifactIds.length === 1 &&
              stage.requiredArtifactIds[0] === stage.observedArtifactIds[0] &&
              stage.artifactEvidence.length === 1 &&
              stage.artifactEvidence[0]?.artifactId ===
                stage.requiredArtifactIds[0] &&
              stage.artifactEvidence[0]?.opened === true &&
              stage.artifactEvidence[0]?.artifactSha256 === artifactSha256 &&
              SHA256.test(stage.artifactEvidence[0]?.validatorLogSha256 ?? ""),
          ),
      ),
    ),
  );
}

function gate(
  blockerCodes: readonly OfficeRoundTripQaBlockerCode[],
): OfficeRoundTripQaGateResult {
  const codes = uniqueSorted(blockerCodes);
  return Object.freeze({
    status: codes.length === 0 ? ("passed" as const) : ("failed" as const),
    blockerCodes: Object.freeze(codes),
  });
}

function externalToolPendingWordGate(): OfficeRoundTripQaGateResult {
  return Object.freeze({
    status: "external_tool_pending_word" as const,
    blockerCodes: Object.freeze([]),
  });
}

export function verifyOfficeRoundTripQa(
  input: VerifyOfficeRoundTripQaInput,
): OfficeRoundTripQaResult {
  const evidenceBlockers: OfficeRoundTripQaBlockerCode[] = [];
  const fieldBlockers: OfficeRoundTripQaBlockerCode[] = [];
  const staticBlockers: OfficeRoundTripQaBlockerCode[] = [];
  const securityBlockers: OfficeRoundTripQaBlockerCode[] = [];
  const schemaBlockers: OfficeRoundTripQaBlockerCode[] = [];
  const visualBlockers: OfficeRoundTripQaBlockerCode[] = [];

  const expected = input.expectedValues;
  let rendererBaseline: OfficeActualFieldReadbackManifest | null = null;
  let actual: OfficeActualFieldReadbackManifest | null = null;
  let rendererStatic: ReturnType<
    typeof buildOfficeVisibleStaticManifestFromDocxBytes
  > | null = null;
  let officeStatic: ReturnType<
    typeof buildOfficeVisibleStaticManifestFromDocxBytes
  > | null = null;
  try {
    rendererBaseline = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: input.rendererOutputDocxBytes,
      expected,
    });
    actual = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: input.officeSavedDocxBytes,
      expected,
    });
    rendererStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: input.rendererOutputDocxBytes,
      expected,
    });
    officeStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: input.officeSavedDocxBytes,
      expected,
    });
  } catch {
    evidenceBlockers.push("OFFICE_QA_EVIDENCE_INVALID");
  }
  if (
    input.syntheticOnly !== true ||
    !validExpectedManifest(expected) ||
    !expectedManifestMatchesCertifiedIr(expected, input.certifiedIr) ||
    sha256OfficeDocxBytes(input.rendererOutputDocxBytes) !==
      expected.rendererOutputDocxSha256 ||
    input.rendererOutputDocxBytes.byteLength !==
      expected.rendererOutputSizeBytes ||
    !rendererBaseline ||
    !validActualManifest(rendererBaseline, expected) ||
    !rendererBaselineMatchesExpected(rendererBaseline, expected) ||
    !actual ||
    !validActualManifest(actual, expected) ||
    sha256OfficeDocxBytes(input.officeSavedDocxBytes) !==
      actual.officeSavedDocxSha256 ||
    input.officeSavedDocxBytes.byteLength !== actual.officeSavedSizeBytes
  ) {
    evidenceBlockers.push("OFFICE_QA_EVIDENCE_INVALID");
  }
  if (
    !validOfficeExecutionEvidence(
      input.officeExecutionEvidence,
      expected,
      actual,
      input.visualMetrics,
    )
  ) {
    evidenceBlockers.push("OFFICE_QA_OFFICE_EXECUTION_FAILED");
  }
  if (
    !validPreOfficeRendererReadbackV2Evidence(
      input.preOfficeRendererReadbackV2Evidence,
      expected,
      input.certifiedIr,
    )
  ) {
    evidenceBlockers.push("OFFICE_QA_PRE_OFFICE_READBACK_FAILED");
  }

  const expectedById = new Map(
    expected.fields.map((field) => [field.fieldId, field]),
  );
  const actualById = new Map(
    (actual?.fields ?? []).map((field) => [field.fieldId, field]),
  );
  const exactFullDocumentVisualSurvival = Boolean(
    actual &&
    visualMetricsProveExactFullDocumentSurvival(
      input.visualMetrics,
      expected.rendererOutputDocxSha256,
      actual.officeSavedDocxSha256,
    ),
  );
  if (
    (actual?.unexpectedBindingCount ?? 1) > 0 ||
    (actual?.ambiguousBindingCount ?? 1) > 0
  ) {
    fieldBlockers.push("OFFICE_QA_UNEXPECTED_FIELD");
  }
  const fieldResults: OfficeFieldSurvivalResult[] = [];
  for (const expectedField of expected.fields) {
    const actualField = actualById.get(expectedField.fieldId);
    if (!actualField) {
      fieldBlockers.push("OFFICE_QA_FIELD_MISSING");
      fieldResults.push(
        Object.freeze({
          fieldId: expectedField.fieldId,
          status: "failed" as const,
          semanticKindMatches: false,
          controlKindMatches: false,
          valueMatches: false,
          observedByteValueMatches: false,
          officeCalculatedPresentation: "none" as const,
          officeCalculatedPresentationVisuallyProven: false,
          behaviorNormalizations: Object.freeze([]),
          controlStateMatches: false,
          occurrenceMatches: false,
          logicalBindingIdentityMatches: false,
          certifiedPartPathTypeOrdinalMatches: false,
          pathNormalizationObserved: false,
          serializationNormalized: false,
          rendererControlSerializationSha256:
            expectedField.rendererControlSerializationSha256,
          outputControlSerializationSha256: null,
          rendererObservedValueSha256:
            expectedField.rendererObservedValueSha256,
          outputObservedValueSha256: null,
        }),
      );
      continue;
    }
    const expectedBinding = expectedField.certifiedBinding;
    const actualBinding = actualField.outputBinding;
    const semanticKindMatches =
      expectedField.semanticKind === actualField.semanticKind;
    const controlKindMatches =
      expectedField.controlKind === actualField.controlKind;
    const valueMatches =
      expectedField.expectedValueSha256 === actualField.actualValueSha256;
    const observedByteValueMatches =
      expectedField.rendererObservedValueSha256 ===
      actualField.outputObservedValueSha256;
    const officeCalculatedPresentationVisuallyProven =
      actualField.officeCalculatedPresentation === "none" ||
      exactFullDocumentVisualSurvival;
    const controlStateMatches =
      expectedField.expectedControlStateSha256 ===
      actualField.actualControlStateSha256;
    const occurrenceMatches =
      expectedField.expectedOccurrences === actualField.actualOccurrences &&
      expectedField.expectedDisposition === actualField.actualDisposition;
    const logicalBindingIdentityMatches =
      expectedBinding.logicalFieldLocatorSha256 ===
      actualBinding.logicalFieldLocatorSha256;
    const certifiedPartPathTypeOrdinalMatches = Boolean(
      expectedBinding.partName === actualBinding.partName &&
      expectedBinding.canonicalPath === actualBinding.canonicalPath &&
      expectedBinding.bindingType === actualBinding.bindingType &&
      expectedBinding.ordinal === actualBinding.ordinal,
    );
    if (!semanticKindMatches || !controlKindMatches) {
      fieldBlockers.push("OFFICE_QA_FIELD_SEMANTICS_CHANGED");
    }
    if (
      !valueMatches ||
      !observedByteValueMatches ||
      !officeCalculatedPresentationVisuallyProven
    ) {
      fieldBlockers.push("OFFICE_QA_FIELD_VALUE_CHANGED");
    }
    if (!controlStateMatches) {
      fieldBlockers.push("OFFICE_QA_CONTROL_STATE_CHANGED");
    }
    if (!occurrenceMatches) {
      fieldBlockers.push("OFFICE_QA_OCCURRENCE_CHANGED");
    }
    if (!logicalBindingIdentityMatches) {
      fieldBlockers.push("OFFICE_QA_BINDING_IDENTITY_LOST");
    }
    fieldResults.push(
      Object.freeze({
        fieldId: expectedField.fieldId,
        status:
          semanticKindMatches &&
          controlKindMatches &&
          valueMatches &&
          observedByteValueMatches &&
          officeCalculatedPresentationVisuallyProven &&
          controlStateMatches &&
          occurrenceMatches &&
          logicalBindingIdentityMatches
            ? ("survived" as const)
            : ("failed" as const),
        semanticKindMatches,
        controlKindMatches,
        valueMatches,
        observedByteValueMatches,
        officeCalculatedPresentation: actualField.officeCalculatedPresentation,
        officeCalculatedPresentationVisuallyProven,
        behaviorNormalizations: actualField.behaviorNormalizations,
        controlStateMatches,
        occurrenceMatches,
        logicalBindingIdentityMatches,
        certifiedPartPathTypeOrdinalMatches,
        pathNormalizationObserved: !certifiedPartPathTypeOrdinalMatches,
        serializationNormalized:
          expectedField.rendererControlSerializationSha256 !==
          actualField.outputControlSerializationSha256,
        rendererControlSerializationSha256:
          expectedField.rendererControlSerializationSha256,
        outputControlSerializationSha256:
          actualField.outputControlSerializationSha256,
        rendererObservedValueSha256: expectedField.rendererObservedValueSha256,
        outputObservedValueSha256: actualField.outputObservedValueSha256,
      }),
    );
  }
  if ([...actualById.keys()].some((fieldId) => !expectedById.has(fieldId))) {
    fieldBlockers.push("OFFICE_QA_UNEXPECTED_FIELD");
  }

  const visibleEvidenceValid = Boolean(
    rendererStatic &&
    officeStatic &&
    validVisibleStaticManifest(rendererStatic.manifest) &&
    validVisibleStaticManifest(officeStatic.manifest) &&
    rendererStatic.manifest.docxSha256 === expected.rendererOutputDocxSha256 &&
    Boolean(actual) &&
    officeStatic.manifest.docxSha256 === actual?.officeSavedDocxSha256,
  );
  if (!visibleEvidenceValid) {
    evidenceBlockers.push("OFFICE_QA_EVIDENCE_INVALID");
  }
  const structuralNormalizationReport =
    rendererStatic && officeStatic
      ? compareOfficeVisibleStaticManifests(
          rendererStatic.manifest,
          officeStatic.manifest,
        )
      : unavailableStructuralNormalizationReport();
  if (!structuralNormalizationReport.aggregateVisibleContentMatches) {
    staticBlockers.push("OFFICE_QA_VISIBLE_STATIC_CHANGED");
  }
  if (!structuralNormalizationReport.aggregateStructureMatches) {
    staticBlockers.push("OFFICE_QA_STATIC_STRUCTURE_CHANGED");
  }

  const security = inspectOfficeDocxSecurityQa(input.officeSavedDocxBytes);
  if (
    security.contractVersion !== OFFICE_PACKAGE_SECURITY_QA_CONTRACT_VERSION ||
    security.inspectorVersion !== OFFICE_PACKAGE_INSPECTOR_SOURCE_VERSION ||
    !actual ||
    security.inspectedDocxSha256 !== actual.officeSavedDocxSha256 ||
    security.inspectedSizeBytes !== actual.officeSavedSizeBytes ||
    !SHA256.test(security.inspectionLogSha256) ||
    !securityEvidenceHashMatches(security) ||
    security.status !== "passed" ||
    security.blockerCodes.length > 0 ||
    security.externalRelationshipCount !== 0 ||
    security.activeContentCount !== 0 ||
    security.embeddedObjectCount !== 0 ||
    !validCount(security.packageEntryCount, 1) ||
    !validCount(security.relationshipCount, 1)
  ) {
    securityBlockers.push("OFFICE_QA_SECURITY_INSPECTION_FAILED");
  }

  const schemaExternalToolPendingWord = Boolean(
    input.schemaEvidence.evidenceClass === OFFICE_QA_EVIDENCE_CLASS &&
    input.schemaEvidence.contractVersion ===
      OFFICE_SCHEMA_QA_CONTRACT_VERSION &&
    input.schemaEvidence.qaOnly === true &&
    input.schemaEvidence.signingEligible === false &&
    input.schemaEvidence.productionStateTransitionEligible === false &&
    input.schemaEvidence.desktopWordApprovalRequired === true &&
    input.schemaEvidence.matrixSha256 ===
      canonicalSha256(input.schemaEvidence.matrix) &&
    schemaEvidenceHashesMatch(input.schemaEvidence, expected, actual) &&
    input.schemaEvidence.status === "external_tool_pending_word" &&
    input.schemaEvidence.compatibilityEngineeringEligible,
  );
  if (
    input.schemaEvidence.evidenceClass !== OFFICE_QA_EVIDENCE_CLASS ||
    input.schemaEvidence.contractVersion !==
      OFFICE_SCHEMA_QA_CONTRACT_VERSION ||
    input.schemaEvidence.qaOnly !== true ||
    input.schemaEvidence.signingEligible !== false ||
    input.schemaEvidence.productionStateTransitionEligible !== false ||
    input.schemaEvidence.desktopWordApprovalRequired !== true ||
    input.schemaEvidence.matrixSha256 !==
      canonicalSha256(input.schemaEvidence.matrix) ||
    !schemaEvidenceHashesMatch(input.schemaEvidence, expected, actual) ||
    (input.schemaEvidence.status !== "passed" && !schemaExternalToolPendingWord)
  ) {
    schemaBlockers.push("OFFICE_QA_SCHEMA_FAILED");
  }

  if (!validVisualMetrics(input.visualMetrics)) {
    evidenceBlockers.push("OFFICE_QA_EVIDENCE_INVALID");
  } else {
    const metrics = input.visualMetrics;
    if (
      metrics.rendererOutputDocxSha256 !== expected.rendererOutputDocxSha256 ||
      metrics.officeSavedDocxSha256 !== actual?.officeSavedDocxSha256 ||
      metrics.originalPdfSourceDocxSha256 !==
        expected.rendererOutputDocxSha256 ||
      metrics.roundTripPdfSourceDocxSha256 !== actual?.officeSavedDocxSha256
    ) {
      evidenceBlockers.push("OFFICE_QA_EVIDENCE_INVALID");
    }
    if (
      metrics.originalPageCount !== metrics.roundTripPageCount ||
      metrics.pages.length !== metrics.originalPageCount
    ) {
      visualBlockers.push("OFFICE_QA_PDF_PAGE_COUNT_CHANGED");
    }
    for (const page of metrics.pages) {
      if (
        page.originalWidthPixels !== page.roundTripWidthPixels ||
        page.originalHeightPixels !== page.roundTripHeightPixels
      ) {
        visualBlockers.push("OFFICE_QA_PDF_GEOMETRY_CHANGED");
      }
      if (
        page.originalHeaderSha256 !== page.roundTripHeaderSha256 ||
        page.originalFooterSha256 !== page.roundTripFooterSha256
      ) {
        visualBlockers.push("OFFICE_QA_PDF_HEADER_FOOTER_CHANGED");
      }
      if (
        page.originalMaskedStaticSha256 !== page.roundTripMaskedStaticSha256 ||
        page.differenceClassification === "static_region_changed"
      ) {
        visualBlockers.push("OFFICE_QA_PDF_STATIC_LAYOUT_CHANGED");
      }
      if (
        page.differenceClassification === "unclassified" ||
        (page.differenceClassification === "field_region_only_reviewed" &&
          !page.humanReviewed) ||
        (page.differenceClassification === "none" && page.differingPixels !== 0)
      ) {
        visualBlockers.push("OFFICE_QA_PDF_DIFFERENCE_UNREVIEWED");
      }
    }
  }

  const gates = Object.freeze({
    fields: gate([...evidenceBlockers, ...fieldBlockers]),
    visibleStatic: gate([...evidenceBlockers, ...staticBlockers]),
    security: gate([...evidenceBlockers, ...securityBlockers]),
    schema:
      evidenceBlockers.length === 0 &&
      schemaBlockers.length === 0 &&
      schemaExternalToolPendingWord
        ? externalToolPendingWordGate()
        : gate([...evidenceBlockers, ...schemaBlockers]),
    visual: gate([...evidenceBlockers, ...visualBlockers]),
  });
  const blockerCodes = uniqueSorted([
    ...evidenceBlockers,
    ...fieldBlockers,
    ...staticBlockers,
    ...securityBlockers,
    ...schemaBlockers,
    ...visualBlockers,
  ]);
  const compatibilityEngineeringEligible = Boolean(
    blockerCodes.length === 0 &&
    Object.values(gates).every(
      (candidate) =>
        candidate.status === "passed" ||
        candidate.status === "external_tool_pending_word",
    ),
  );
  const postOfficeSavedObservedStatus = [
    "passed",
    "failed",
    "not_run",
  ].includes(input.postOfficeSavedReadbackV2Status)
    ? input.postOfficeSavedReadbackV2Status
    : "not_run";
  const resultWithoutHash = {
    evidenceClass: OFFICE_QA_EVIDENCE_CLASS,
    contractVersion: OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
    qaOnly: true as const,
    signingEligible: false as const,
    productionStateTransitionEligible: false as const,
    mayReplaceProductionReadbackV2: false as const,
    mayAuthorizeSigning: false as const,
    mayAuthorizeExportOrDownload: false as const,
    status: !compatibilityEngineeringEligible
      ? ("failed" as const)
      : schemaExternalToolPendingWord
        ? ("external_tool_pending_word" as const)
        : ("passed" as const),
    compatibilityEngineeringEligible,
    officeCompatibilityApproved: false as const,
    desktopWordApprovalStatus: "pending" as const,
    blockerCodes: Object.freeze(blockerCodes),
    gates,
    fields: Object.freeze(
      fieldResults.sort((left, right) =>
        left.fieldId.localeCompare(right.fieldId),
      ),
    ),
    rendererBaselineReadbackManifestSha256:
      rendererBaseline?.manifestSha256 ?? null,
    officeSavedReadbackManifestSha256: actual?.manifestSha256 ?? null,
    rendererVisibleStaticEvidenceSha256:
      rendererStatic?.byteEvidence.evidenceSha256 ?? null,
    officeSavedVisibleStaticEvidenceSha256:
      officeStatic?.byteEvidence.evidenceSha256 ?? null,
    securityInspectionEvidenceSha256: security.evidenceSha256,
    officeExecutionEvidenceSha256:
      input.officeExecutionEvidence?.evidenceSha256 ?? null,
    structuralNormalizationReport,
    schemaEvidenceMatrixSha256: input.schemaEvidence.matrixSha256,
    readbackV2Boundary: Object.freeze({
      preOfficeRendererStatus: "passed" as const,
      preOfficeRendererEvidenceSha256:
        input.preOfficeRendererReadbackV2Evidence?.evidenceSha256 ?? "",
      postOfficeSavedObservedStatus,
      qaResultDoesNotChangeProductionStatus: true as const,
    }),
  };
  return Object.freeze({
    ...resultWithoutHash,
    resultSha256: canonicalSha256(resultWithoutHash),
  });
}
