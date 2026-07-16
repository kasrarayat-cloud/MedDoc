import { createHash } from "node:crypto";

import { canonicalSha256 } from "../template-twin/canonical";
import type {
  FieldResolution,
  RendererBinding,
  TemplateDocIR,
  TemplateField,
} from "../template-twin/ir";
import {
  certifiedBindingFingerprintSha256,
  deriveOrdinaryPlaceholderBinding,
  deriveOoxmlBindingIdentity,
  deriveTableLocation,
  indexBindingXmlPart,
  nativeIdentityFromRendererBinding,
  type BindingTableLocation,
  type IndexedBindingNode,
  type IndexedBindingPart,
  type NativeBindingIdentity,
} from "./binding-fingerprint";
import { inspectDocxPackage } from "./package-security";
import {
  WORDPROCESSINGML_2010_NAMESPACE,
  WORDPROCESSINGML_NAMESPACE,
  childrenOf,
  decodeXmlScalar,
  exactExpandedAttribute,
  parseOrderedXml,
  tagOf,
  type OrderedXmlNode,
} from "./xml";

export const OFFICE_DOCX_BYTE_READBACK_QA_VERSION =
  "template-twin-office-byte-readback-qa/1.2.0" as const;
export const OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION =
  "template-twin-office-roundtrip-qa/2.2.0" as const;
export const OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION =
  "template-twin-office-field-readback-qa/2.2.0" as const;

export type OfficeQaControlKind =
  | "text_content_control"
  | "dropdown_content_control"
  | "combo_box_content_control"
  | "date_content_control"
  | "checkbox_content_control"
  | "legacy_text"
  | "legacy_dropdown"
  | "legacy_date"
  | "legacy_checkbox"
  | "fixed_table_cell"
  | "ordinary_placeholder_text";

export type OfficeCalculatedPresentation =
  | "none"
  | "libreoffice_legacy_dropdown";

export interface OfficeCertifiedBindingExpectation {
  readonly partName: string;
  readonly canonicalPath: string;
  readonly bindingType:
    | "content_control"
    | "legacy_form_field"
    | "table_cell"
    | "ordinary_placeholder";
  readonly bindingProfile?: RendererBinding["bindingProfile"];
  readonly ordinaryPlaceholder?: RendererBinding["ordinaryPlaceholder"];
  readonly ordinaryOfficeContext?: {
    readonly logicalRegionId: string;
    readonly visiblePrefixLength: number;
    readonly visibleSuffixLength: number;
    readonly visiblePrefixSha256: string;
    readonly visibleSuffixSha256: string;
    readonly visibleStaticContextSha256: string;
  };
  readonly ordinal: number;
  readonly certifiedBindingSha256: string;
  readonly nativeIdentity: NativeBindingIdentity;
  readonly sourceControlSha256: string;
  readonly sourceBindingIdentitySha256: string;
  readonly tableLocation: BindingTableLocation;
  readonly canonicalRepeatAncestorPath: string | null;
  readonly labelContextSha256: string;
  /** Recomputed from certified identity data, never supplied independently. */
  readonly logicalFieldLocatorSha256: string;
}

export interface OfficeExpectedFieldValue {
  readonly fieldId: string;
  readonly semanticKind: string;
  readonly controlKind: OfficeQaControlKind;
  readonly expectedValueSha256: string;
  /** Actual renderer-byte value, including unresolved placeholder/control state. */
  readonly rendererObservedValueSha256: string;
  readonly expectedControlStateSha256: string;
  readonly rendererControlSerializationSha256: string;
  readonly expectedOccurrences: 1;
  readonly expectedDisposition:
    | "rendered"
    | "unresolved_blank"
    | "preserved_unresolved";
  readonly certifiedBinding: OfficeCertifiedBindingExpectation;
}

export interface OfficeExpectedValueManifest {
  readonly contractVersion: typeof OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION;
  readonly byteReadbackVersion: typeof OFFICE_DOCX_BYTE_READBACK_QA_VERSION;
  readonly syntheticOnly: true;
  readonly sourceDocxSha256: string;
  readonly rendererOutputDocxSha256: string;
  readonly rendererOutputSizeBytes: number;
  readonly irStructureSha256: string;
  readonly irFieldIdsSha256: string;
  readonly expectedIrFieldCount: number;
  readonly fields: readonly OfficeExpectedFieldValue[];
  readonly manifestSha256: string;
}

export interface OfficeActualFieldReadback {
  readonly fieldId: string;
  readonly semanticKind: string;
  readonly controlKind: OfficeQaControlKind;
  readonly actualValueSha256: string;
  /** Actual Office-saved byte value before clinical-disposition normalization. */
  readonly outputObservedValueSha256: string;
  readonly actualControlStateSha256: string;
  readonly outputControlSerializationSha256: string;
  readonly actualOccurrences: number;
  readonly actualDisposition: OfficeExpectedFieldValue["expectedDisposition"];
  readonly officeCalculatedPresentation: OfficeCalculatedPresentation;
  readonly behaviorNormalizations: readonly (
    | "calendar_omitted_defaults_gregorian"
    | "store_mapped_data_as_not_applicable_unbound"
  )[];
  readonly outputBinding: {
    readonly partName: string;
    readonly canonicalPath: string;
    readonly bindingType: OfficeCertifiedBindingExpectation["bindingType"];
    readonly ordinal: number;
    readonly logicalFieldLocatorSha256: string;
    readonly outputBindingIdentitySha256: string;
    readonly tableLocation: BindingTableLocation;
  };
}

export interface OfficeActualFieldReadbackManifest {
  readonly contractVersion: typeof OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION;
  readonly byteReadbackVersion: typeof OFFICE_DOCX_BYTE_READBACK_QA_VERSION;
  readonly syntheticOnly: true;
  readonly readFrom: "COMPLETED_OFFICE_SAVED_DOCX_BYTES";
  readonly officeSavedDocxSha256: string;
  readonly officeSavedSizeBytes: number;
  readonly expectedManifestSha256: string;
  readonly irFieldIdsSha256: string;
  readonly fields: readonly OfficeActualFieldReadback[];
  readonly unexpectedBindingCount: number;
  readonly ambiguousBindingCount: number;
  readonly manifestSha256: string;
}

export interface BuildOfficeExpectedValueManifestInput {
  readonly syntheticOnly: true;
  readonly sourceDocxBytes: Uint8Array;
  readonly rendererOutputDocxBytes: Uint8Array;
  readonly ir: TemplateDocIR;
  readonly resolutions: readonly FieldResolution[];
}

export interface OfficeByteDerivedVisibleStaticRegion {
  readonly logicalRegionId: string;
  readonly role: "main_document" | "header" | "footer";
  readonly partName: string;
  readonly visibleTokens: readonly string[];
  readonly structuralTokens: readonly string[];
}

export interface OfficeByteDerivedVisibleStaticEvidence {
  readonly syntheticOnly: true;
  readonly byteReadbackVersion: typeof OFFICE_DOCX_BYTE_READBACK_QA_VERSION;
  readonly docxSha256: string;
  readonly docxSizeBytes: number;
  readonly expectedManifestSha256: string;
  readonly regions: readonly OfficeByteDerivedVisibleStaticRegion[];
  readonly evidenceSha256: string;
}

interface IndexedPackagePart {
  readonly partName: string;
  readonly part: IndexedBindingPart;
  readonly logicalRegionId: string;
  readonly role: "main_document" | "header" | "footer";
}

interface LocatedField {
  readonly expected: OfficeExpectedFieldValue;
  readonly indexedPart: IndexedPackagePart;
  readonly node: IndexedBindingNode;
  readonly bindingIdentitySha256: string;
  readonly nativeIdentity: NativeBindingIdentity;
  readonly tableLocation: BindingTableLocation;
  readonly actualOccurrences: number;
  readonly ordinaryOfficeCandidate?: OrdinaryOfficeCandidate;
  ordinal: number;
}

interface OrdinaryOfficeCandidate {
  readonly value: string;
  readonly prefix: string;
  readonly suffix: string;
  readonly identitySha256: string;
}

const SHA256 = /^[a-f0-9]{64}$/;
const OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE =
  "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

export function sha256OfficeDocxBytes(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

export function hashOfficeQaSemanticValue(
  fieldId: string,
  value: unknown,
): string {
  return canonicalSha256({
    qaContract: OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
    fieldId,
    value,
  });
}

export function hashOfficeQaControlState(
  fieldId: string,
  controlState: unknown,
): string {
  return canonicalSha256({
    qaContract: OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
    fieldId,
    controlState,
  });
}

/**
 * Creates the baseline only after independently reopening the completed
 * renderer output. This prevents a caller-provided value/control hash from
 * manufacturing Office compatibility evidence.
 */
export function buildOfficeExpectedValueManifest(
  input: BuildOfficeExpectedValueManifestInput,
): OfficeExpectedValueManifest {
  if (
    input.syntheticOnly !== true ||
    input.ir.fields.length === 0 ||
    input.ir.fields.some(
      (field) =>
        field.detectionStatus === "unsupported" ||
        field.rowPrototype ||
        field.rendererBinding.bindingType === "repeating_row",
    )
  ) {
    throw new Error("Office QA requires a nonempty, supported synthetic IR.");
  }
  const sourceDocxSha256 = sha256OfficeDocxBytes(input.sourceDocxBytes);
  if (
    sourceDocxSha256 !== input.ir.source.sha256 ||
    input.sourceDocxBytes.byteLength !== input.ir.source.sizeBytes
  ) {
    throw new Error("Office QA source bytes do not match the certified IR.");
  }
  const resolutions = new Map(
    input.resolutions.map((resolution) => [resolution.fieldId, resolution]),
  );
  if (
    resolutions.size !== input.ir.fields.length ||
    input.resolutions.length !== input.ir.fields.length ||
    input.ir.fields.some((field) => !resolutions.has(field.fieldId))
  ) {
    throw new Error("Office QA requires one resolution for every IR field.");
  }

  const rendererOutputDocxSha256 = sha256OfficeDocxBytes(
    input.rendererOutputDocxBytes,
  );
  assertNoCustomXmlParts(input.rendererOutputDocxBytes);
  const packageParts = indexStructuralPackageParts(
    input.rendererOutputDocxBytes,
  );
  const expectedFields = input.ir.fields.map((field) => {
    assertCertifiedBinding(field);
    const resolution = resolutions.get(field.fieldId)!;
    const located = locateAtCertifiedRendererPath(packageParts, field);
    const read = readLocatedValue(
      located.indexedPart.part,
      located.node,
      field,
    );
    if (read.officeCalculatedPresentation) {
      throw new Error(
        `Renderer baseline cannot use Office-calculated presentation for ${field.fieldId}.`,
      );
    }
    const expectedDisposition = dispositionFor(field, resolution);
    const baselineValue = valueForDisposition(read.value, expectedDisposition);
    if (
      hashOfficeQaSemanticValue(field.fieldId, baselineValue) !==
      hashOfficeQaSemanticValue(field.fieldId, resolution.value)
    ) {
      throw new Error(`Renderer baseline value mismatch for ${field.fieldId}.`);
    }
    return Object.freeze({
      fieldId: field.fieldId,
      semanticKind: field.kind,
      controlKind: read.controlKind,
      expectedValueSha256: hashOfficeQaSemanticValue(
        field.fieldId,
        baselineValue,
      ),
      rendererObservedValueSha256: hashOfficeQaSemanticValue(
        field.fieldId,
        read.value,
      ),
      expectedControlStateSha256: hashOfficeQaControlState(
        field.fieldId,
        read.controlState,
      ),
      rendererControlSerializationSha256: read.rawSerializationSha256,
      expectedOccurrences: 1 as const,
      expectedDisposition,
      certifiedBinding: located.expected.certifiedBinding,
    });
  });
  expectedFields.sort((left, right) =>
    left.fieldId.localeCompare(right.fieldId),
  );
  const irFieldIds = [...input.ir.fields.map((field) => field.fieldId)].sort();
  const unsigned = {
    contractVersion: OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION,
    byteReadbackVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
    syntheticOnly: true as const,
    sourceDocxSha256,
    rendererOutputDocxSha256,
    rendererOutputSizeBytes: input.rendererOutputDocxBytes.byteLength,
    irStructureSha256: input.ir.structureSha256,
    irFieldIdsSha256: canonicalSha256(irFieldIds),
    expectedIrFieldCount: input.ir.fields.length,
    fields: Object.freeze(expectedFields),
  };
  return Object.freeze({
    ...unsigned,
    manifestSha256: canonicalSha256(unsigned),
  });
}

/** Independently extracts logical field evidence from completed DOCX bytes. */
export function readOfficeSavedDocxFieldsQa(input: {
  readonly syntheticOnly: true;
  readonly officeSavedDocxBytes: Uint8Array;
  readonly expected: OfficeExpectedValueManifest;
}): OfficeActualFieldReadbackManifest {
  if (input.syntheticOnly !== true || !validExpectedManifest(input.expected)) {
    throw new Error("Invalid Office QA expected-value evidence.");
  }
  const officeSavedDocxSha256 = sha256OfficeDocxBytes(
    input.officeSavedDocxBytes,
  );
  assertNoCustomXmlParts(input.officeSavedDocxBytes);
  const packageParts = indexStructuralPackageParts(input.officeSavedDocxBytes);
  const located: LocatedField[] = [];
  let ambiguousBindingCount = 0;
  for (const expected of input.expected.fields) {
    const matches = locateLogicalOutputBindings(packageParts, expected);
    if (matches.length !== 1) {
      ambiguousBindingCount += 1;
      continue;
    }
    located.push({ ...matches[0]!, ordinal: -1 });
  }
  const partOrder = new Map(
    packageParts.map((candidate, index) => [candidate.partName, index]),
  );
  [...located]
    .sort(
      (left, right) =>
        (partOrder.get(left.indexedPart.partName) ?? Number.MAX_SAFE_INTEGER) -
          (partOrder.get(right.indexedPart.partName) ??
            Number.MAX_SAFE_INTEGER) || left.node.order - right.node.order,
    )
    .forEach((record, ordinal) => {
      record.ordinal = ordinal;
    });

  const fields = located.map((record) => {
    const read = record.ordinaryOfficeCandidate
      ? readOrdinaryOfficeLocatedValue(record)
      : readLocatedValue(
          record.indexedPart.part,
          record.node,
          expectedFieldShape(record.expected),
        );
    const actualValue = valueForDisposition(
      read.value,
      record.expected.expectedDisposition,
    );
    return Object.freeze({
      fieldId: record.expected.fieldId,
      semanticKind: record.expected.semanticKind,
      controlKind: read.controlKind,
      actualValueSha256: hashOfficeQaSemanticValue(
        record.expected.fieldId,
        actualValue,
      ),
      outputObservedValueSha256: hashOfficeQaSemanticValue(
        record.expected.fieldId,
        read.value,
      ),
      actualControlStateSha256: hashOfficeQaControlState(
        record.expected.fieldId,
        read.controlState,
      ),
      outputControlSerializationSha256: read.rawSerializationSha256,
      actualOccurrences: record.actualOccurrences,
      actualDisposition: record.expected.expectedDisposition,
      officeCalculatedPresentation: read.officeCalculatedPresentation ?? "none",
      behaviorNormalizations: Object.freeze(
        [...(read.behaviorNormalizations ?? [])].sort(),
      ),
      outputBinding: Object.freeze({
        partName: record.indexedPart.partName,
        canonicalPath: record.node.canonicalPath,
        bindingType: record.expected.certifiedBinding.bindingType,
        ordinal: record.ordinal,
        logicalFieldLocatorSha256: logicalFieldLocatorSha256({
          fieldId: record.expected.fieldId,
          bindingType: record.expected.certifiedBinding.bindingType,
          nativeIdentity: record.nativeIdentity,
          controlKind: read.controlKind,
          tableLocation: record.tableLocation,
          labelContextSha256:
            record.expected.certifiedBinding.labelContextSha256,
        }),
        outputBindingIdentitySha256: record.bindingIdentitySha256,
        tableLocation: record.tableLocation,
      }),
    });
  });
  fields.sort((left, right) => left.fieldId.localeCompare(right.fieldId));
  const expectedLocatorKeys = new Set(
    input.expected.fields.map(
      (field) => field.certifiedBinding.logicalFieldLocatorSha256,
    ),
  );
  const actualNativeLocators = censusNativeLogicalLocators(
    packageParts,
    input.expected.fields,
  );
  const unexpectedBindingCount = actualNativeLocators.filter(
    (locator) => !expectedLocatorKeys.has(locator),
  ).length;
  const unsigned = {
    contractVersion: OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION,
    byteReadbackVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
    syntheticOnly: true as const,
    readFrom: "COMPLETED_OFFICE_SAVED_DOCX_BYTES" as const,
    officeSavedDocxSha256,
    officeSavedSizeBytes: input.officeSavedDocxBytes.byteLength,
    expectedManifestSha256: input.expected.manifestSha256,
    irFieldIdsSha256: input.expected.irFieldIdsSha256,
    fields: Object.freeze(fields),
    unexpectedBindingCount,
    ambiguousBindingCount,
  };
  return Object.freeze({
    ...unsigned,
    manifestSha256: canonicalSha256(unsigned),
  });
}

/**
 * Builds normalized visible/static tokens directly from DOCX bytes while
 * masking only independently located certified field regions.
 */
export function deriveOfficeVisibleStaticFromDocxBytesQa(input: {
  readonly syntheticOnly: true;
  readonly docxBytes: Uint8Array;
  readonly expected: OfficeExpectedValueManifest;
}): OfficeByteDerivedVisibleStaticEvidence {
  if (input.syntheticOnly !== true || !validExpectedManifest(input.expected)) {
    throw new Error("Invalid Office QA static-region input.");
  }
  const packageParts = indexStructuralPackageParts(input.docxBytes);
  const located = input.expected.fields.map((field) => {
    const matches = locateLogicalOutputBindings(packageParts, field);
    if (matches.length !== 1) {
      throw new Error(`Static mask binding is not unique: ${field.fieldId}.`);
    }
    return matches[0]!;
  });
  const regions: OfficeByteDerivedVisibleStaticRegion[] = [];
  for (const packagePart of packageParts) {
    const partLocated = located.filter(
      (field) => field.indexedPart.partName === packagePart.partName,
    );
    const maskedNodes = maskedVisibleNodes(packagePart.part, partLocated);
    const markers = new Map(
      partLocated.map((field) => [
        field.node,
        `certified-field:${field.expected.fieldId}:${field.expected.controlKind}`,
      ]),
    );
    const visibleTokens: string[] = [];
    const structuralTokens: string[] = [];
    for (const node of packagePart.part.nodes) {
      const marker = markers.get(node);
      if (marker) {
        structuralTokens.push(marker);
        const ordinary = partLocated.find(
          (field) =>
            field.node === node &&
            field.expected.certifiedBinding.bindingType ===
              "ordinary_placeholder",
        );
        if (ordinary) {
          const candidate =
            ordinary.ordinaryOfficeCandidate ??
            readOrdinaryOfficeCandidate(
              ordinary.indexedPart,
              ordinary.node,
              ordinary.expected,
            );
          if (!candidate) {
            throw new Error(
              `Ordinary-placeholder static context is invalid: ${ordinary.expected.fieldId}.`,
            );
          }
          visibleTokens.push(candidate.prefix, candidate.suffix);
          structuralTokens.push(
            `ordinary-placeholder-static:${canonicalSha256({
              logicalRegionId: ordinary.indexedPart.logicalRegionId,
              tableLocation: ordinary.tableLocation,
              visiblePrefixSha256: canonicalSha256(candidate.prefix),
              visibleSuffixSha256: canonicalSha256(candidate.suffix),
              visibleStaticContextSha256: canonicalSha256({
                prefix: candidate.prefix,
                suffix: candidate.suffix,
              }),
            })}`,
          );
        }
      }
      if (node.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
      if (node.visit.localName === "t" && !maskedNodes.has(node)) {
        visibleTokens.push(nodeText(node.node));
        structuralTokens.push(
          `static-run-format:${canonicalSha256(
            staticRunFormattingDescriptor(packagePart.part, node),
          )}`,
        );
      } else if (
        (node.visit.localName === "tab" ||
          node.visit.localName === "br" ||
          node.visit.localName === "cr") &&
        !maskedNodes.has(node)
      ) {
        visibleTokens.push(node.visit.localName === "tab" ? "\t" : "\n");
      }
      const structural = normalizedStaticStructureToken(packagePart.part, node);
      if (structural) structuralTokens.push(structural);
    }
    const role = packagePart.role;
    const logicalRegionId = packagePart.logicalRegionId;
    regions.push(
      Object.freeze({
        logicalRegionId,
        role,
        partName: packagePart.partName,
        visibleTokens: Object.freeze(visibleTokens),
        structuralTokens: Object.freeze(structuralTokens),
      }),
    );
  }
  const unsigned = {
    syntheticOnly: true as const,
    byteReadbackVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
    docxSha256: sha256OfficeDocxBytes(input.docxBytes),
    docxSizeBytes: input.docxBytes.byteLength,
    expectedManifestSha256: input.expected.manifestSha256,
    regions: Object.freeze(regions),
  };
  return Object.freeze({
    ...unsigned,
    evidenceSha256: canonicalSha256(unsigned),
  });
}

export function validExpectedManifest(
  manifest: OfficeExpectedValueManifest,
): boolean {
  const { manifestSha256, ...unsigned } = manifest;
  const ids = manifest.fields.map((field) => field.fieldId).sort();
  return Boolean(
    manifest.contractVersion === OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION &&
    manifest.byteReadbackVersion === OFFICE_DOCX_BYTE_READBACK_QA_VERSION &&
    manifest.syntheticOnly === true &&
    SHA256.test(manifest.sourceDocxSha256) &&
    SHA256.test(manifest.rendererOutputDocxSha256) &&
    Number.isSafeInteger(manifest.rendererOutputSizeBytes) &&
    manifest.rendererOutputSizeBytes > 0 &&
    SHA256.test(manifest.irStructureSha256) &&
    SHA256.test(manifest.irFieldIdsSha256) &&
    manifest.fields.length > 0 &&
    manifest.expectedIrFieldCount === manifest.fields.length &&
    new Set(ids).size === ids.length &&
    manifest.irFieldIdsSha256 === canonicalSha256(ids) &&
    manifest.fields.every(validExpectedField) &&
    SHA256.test(manifestSha256) &&
    manifestSha256 === canonicalSha256(unsigned),
  );
}

export function validActualManifest(
  manifest: OfficeActualFieldReadbackManifest,
  expected: OfficeExpectedValueManifest,
): boolean {
  const { manifestSha256, ...unsigned } = manifest;
  return Boolean(
    manifest.contractVersion === OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION &&
    manifest.byteReadbackVersion === OFFICE_DOCX_BYTE_READBACK_QA_VERSION &&
    manifest.syntheticOnly === true &&
    manifest.readFrom === "COMPLETED_OFFICE_SAVED_DOCX_BYTES" &&
    SHA256.test(manifest.officeSavedDocxSha256) &&
    Number.isSafeInteger(manifest.officeSavedSizeBytes) &&
    manifest.officeSavedSizeBytes > 0 &&
    manifest.expectedManifestSha256 === expected.manifestSha256 &&
    manifest.irFieldIdsSha256 === expected.irFieldIdsSha256 &&
    Number.isSafeInteger(manifest.unexpectedBindingCount) &&
    manifest.unexpectedBindingCount >= 0 &&
    Number.isSafeInteger(manifest.ambiguousBindingCount) &&
    manifest.ambiguousBindingCount >= 0 &&
    manifest.fields.every(validActualField) &&
    manifest.fields.length === expected.fields.length &&
    canonicalSha256(
      [...manifest.fields.map((field) => field.fieldId)].sort(),
    ) === expected.irFieldIdsSha256 &&
    SHA256.test(manifestSha256) &&
    manifestSha256 === canonicalSha256(unsigned),
  );
}

function validExpectedField(field: OfficeExpectedFieldValue): boolean {
  const binding = field.certifiedBinding;
  return Boolean(
    field.fieldId.length > 0 &&
    field.semanticKind.length > 0 &&
    SHA256.test(field.expectedValueSha256) &&
    SHA256.test(field.rendererObservedValueSha256) &&
    SHA256.test(field.expectedControlStateSha256) &&
    SHA256.test(field.rendererControlSerializationSha256) &&
    field.expectedOccurrences === 1 &&
    SHA256.test(binding.certifiedBindingSha256) &&
    SHA256.test(binding.sourceControlSha256) &&
    SHA256.test(binding.sourceBindingIdentitySha256) &&
    SHA256.test(binding.labelContextSha256) &&
    SHA256.test(binding.logicalFieldLocatorSha256) &&
    (binding.bindingProfile === undefined ||
      binding.bindingProfile === "TAB_ONLY_BLANK_TABLE_CELL_V1" ||
      binding.bindingProfile === "ORDINARY_PLACEHOLDER_TOKEN_V1") &&
    (binding.bindingType === "ordinary_placeholder"
      ? Boolean(
          binding.ordinaryPlaceholder &&
          binding.ordinaryOfficeContext &&
          binding.ordinaryOfficeContext.logicalRegionId.length > 0 &&
          Number.isSafeInteger(
            binding.ordinaryOfficeContext.visiblePrefixLength,
          ) &&
          binding.ordinaryOfficeContext.visiblePrefixLength >= 0 &&
          Number.isSafeInteger(
            binding.ordinaryOfficeContext.visibleSuffixLength,
          ) &&
          binding.ordinaryOfficeContext.visibleSuffixLength >= 0 &&
          SHA256.test(binding.ordinaryOfficeContext.visiblePrefixSha256) &&
          SHA256.test(binding.ordinaryOfficeContext.visibleSuffixSha256) &&
          SHA256.test(binding.ordinaryOfficeContext.visibleStaticContextSha256),
        )
      : binding.ordinaryPlaceholder === undefined &&
        binding.ordinaryOfficeContext === undefined) &&
    binding.certifiedBindingSha256 ===
      certifiedBindingFingerprintSha256({
        fieldId: field.fieldId,
        partName: binding.partName,
        canonicalPath: binding.canonicalPath,
        bindingType: binding.bindingType,
        bindingProfile: binding.bindingProfile,
        ordinaryPlaceholder: binding.ordinaryPlaceholder,
        bindingOrdinal: binding.ordinal,
        nativeIdentity: binding.nativeIdentity,
        sourceControlSha256: binding.sourceControlSha256,
        sourceBindingIdentitySha256: binding.sourceBindingIdentitySha256,
        tableLocation: binding.tableLocation,
        canonicalRepeatAncestorPath: binding.canonicalRepeatAncestorPath,
      }) &&
    binding.logicalFieldLocatorSha256 ===
      logicalFieldLocatorSha256({
        fieldId: field.fieldId,
        bindingType: binding.bindingType,
        nativeIdentity: binding.nativeIdentity,
        controlKind: field.controlKind,
        tableLocation: binding.tableLocation,
        labelContextSha256: binding.labelContextSha256,
      }),
  );
}

function validActualField(field: OfficeActualFieldReadback): boolean {
  return Boolean(
    field.fieldId.length > 0 &&
    field.semanticKind.length > 0 &&
    SHA256.test(field.actualValueSha256) &&
    SHA256.test(field.outputObservedValueSha256) &&
    SHA256.test(field.actualControlStateSha256) &&
    SHA256.test(field.outputControlSerializationSha256) &&
    Number.isSafeInteger(field.actualOccurrences) &&
    field.actualOccurrences > 0 &&
    field.outputBinding.partName.length > 0 &&
    ["none", "libreoffice_legacy_dropdown"].includes(
      field.officeCalculatedPresentation,
    ) &&
    new Set(field.behaviorNormalizations).size ===
      field.behaviorNormalizations.length &&
    field.behaviorNormalizations.every((normalization) =>
      [
        "calendar_omitted_defaults_gregorian",
        "store_mapped_data_as_not_applicable_unbound",
      ].includes(normalization),
    ) &&
    field.outputBinding.canonicalPath.length > 0 &&
    Number.isSafeInteger(field.outputBinding.ordinal) &&
    field.outputBinding.ordinal >= 0 &&
    SHA256.test(field.outputBinding.logicalFieldLocatorSha256) &&
    SHA256.test(field.outputBinding.outputBindingIdentitySha256),
  );
}

function certifiedExpectation(
  field: TemplateField,
  controlKind: OfficeQaControlKind,
  located?: {
    indexedPart: IndexedPackagePart;
    node: IndexedBindingNode;
  },
): OfficeCertifiedBindingExpectation {
  const binding = field.rendererBinding;
  const nativeIdentity = nativeIdentityFromRendererBinding(binding);
  const tableLocation = bindingTableLocation(binding);
  return Object.freeze({
    partName: binding.partName,
    canonicalPath: binding.canonicalPath,
    bindingType: supportedBindingType(binding.bindingType),
    ...(binding.bindingProfile === undefined
      ? {}
      : { bindingProfile: binding.bindingProfile }),
    ...(binding.ordinaryPlaceholder === undefined
      ? {}
      : { ordinaryPlaceholder: binding.ordinaryPlaceholder }),
    ...(binding.bindingType === "ordinary_placeholder" && located
      ? {
          ordinaryOfficeContext: deriveOrdinaryOfficeContext(
            located.indexedPart,
            located.node,
            field,
          ),
        }
      : {}),
    ordinal: binding.ordinal,
    certifiedBindingSha256: binding.certifiedBindingSha256,
    nativeIdentity,
    sourceControlSha256: binding.sourceControlSha256,
    sourceBindingIdentitySha256: binding.sourceBindingIdentitySha256,
    tableLocation,
    canonicalRepeatAncestorPath: binding.canonicalRepeatAncestorPath,
    labelContextSha256: canonicalSha256(field.originalLabel),
    logicalFieldLocatorSha256: logicalFieldLocatorSha256({
      fieldId: field.fieldId,
      bindingType: supportedBindingType(binding.bindingType),
      nativeIdentity,
      controlKind,
      tableLocation,
      labelContextSha256: canonicalSha256(field.originalLabel),
    }),
  });
}

function assertCertifiedBinding(field: TemplateField): void {
  const binding = field.rendererBinding;
  const bindingType = supportedBindingType(binding.bindingType);
  const nativeIdentity = nativeIdentityFromRendererBinding(binding);
  const tableLocation = bindingTableLocation(binding);
  if (
    binding.certifiedBindingSha256 !==
    certifiedBindingFingerprintSha256({
      fieldId: field.fieldId,
      partName: binding.partName,
      canonicalPath: binding.canonicalPath,
      bindingType,
      bindingProfile: binding.bindingProfile,
      ordinaryPlaceholder: binding.ordinaryPlaceholder,
      bindingOrdinal: binding.ordinal,
      nativeIdentity,
      sourceControlSha256: binding.sourceControlSha256,
      sourceBindingIdentitySha256: binding.sourceBindingIdentitySha256,
      tableLocation,
      canonicalRepeatAncestorPath: binding.canonicalRepeatAncestorPath,
    })
  ) {
    throw new Error(`Invalid certified binding for ${field.fieldId}.`);
  }
}

function logicalFieldLocatorSha256(input: {
  fieldId: string;
  bindingType: OfficeCertifiedBindingExpectation["bindingType"];
  nativeIdentity: NativeBindingIdentity;
  controlKind: OfficeQaControlKind;
  tableLocation: BindingTableLocation;
  labelContextSha256: string;
}): string {
  return canonicalSha256({
    qaVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
    fieldId: input.fieldId,
    bindingType: input.bindingType,
    nativeIdentity: input.nativeIdentity,
    controlKind: input.controlKind,
    tableLocation: input.tableLocation,
    labelContextSha256: input.labelContextSha256,
  });
}

function bindingTableLocation(binding: RendererBinding): BindingTableLocation {
  return {
    tableIndex: binding.tableIndex,
    rowIndex: binding.rowIndex,
    cellIndex: binding.cellIndex,
  };
}

function supportedBindingType(
  bindingType: RendererBinding["bindingType"],
): OfficeCertifiedBindingExpectation["bindingType"] {
  if (bindingType === "repeating_row") {
    throw new Error("This binding is not yet eligible for Office QA.");
  }
  return bindingType;
}

function dispositionFor(
  field: TemplateField,
  resolution: FieldResolution,
): OfficeExpectedFieldValue["expectedDisposition"] {
  if (resolution.value !== null) return "rendered";
  return field.kind === "checkbox" ||
    field.rendererBinding.bindingType === "ordinary_placeholder"
    ? "preserved_unresolved"
    : "unresolved_blank";
}

function indexStructuralPackageParts(bytes: Uint8Array): IndexedPackagePart[] {
  const inspected = inspectDocxPackage(bytes);
  const mainEntry = inspected.zip.entries.get(inspected.mainPartName);
  if (!mainEntry) throw new Error("Missing main document part.");
  const mainPart = indexBindingXmlPart(
    parseOrderedXml(mainEntry.bytes, inspected.limits),
  );
  const settingsEntry = inspected.zip.entries.get("word/settings.xml");
  const settingsPart = settingsEntry
    ? indexBindingXmlPart(
        parseOrderedXml(settingsEntry.bytes, inspected.limits),
      )
    : null;
  const evenHeadersEnabled = Boolean(
    settingsPart?.nodes.some(
      (node) =>
        isWordElement(node, "evenAndOddHeaders") && wordOnOffEnabled(node),
    ),
  );
  const firstHeadersEnabled = mainPart.nodes.some(
    (node) => isWordElement(node, "titlePg") && wordOnOffEnabled(node),
  );
  const counters = new Map<string, number>();
  const descriptors: Array<{
    partName: string;
    logicalRegionId: string;
    role: IndexedPackagePart["role"];
  }> = [
    {
      partName: inspected.mainPartName,
      logicalRegionId: "main-document",
      role: "main_document",
    },
  ];
  for (const node of mainPart.nodes) {
    const role = isWordElement(node, "headerReference")
      ? ("header" as const)
      : isWordElement(node, "footerReference")
        ? ("footer" as const)
        : null;
    if (!role) continue;
    const referenceType = wordAttribute(node, "type") ?? "default";
    if (
      (referenceType === "even" && !evenHeadersEnabled) ||
      (referenceType === "first" && !firstHeadersEnabled)
    ) {
      continue;
    }
    if (!["default", "even", "first"].includes(referenceType)) {
      throw new Error("Unknown header/footer reference type.");
    }
    const relationshipId = exactExpandedAttribute(
      node.visit,
      OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE,
      "id",
    );
    const relationship = inspected.relationships.find(
      (candidate) =>
        candidate.sourcePartName === inspected.mainPartName &&
        candidate.id === relationshipId &&
        candidate.type.endsWith(`/${role}`),
    );
    if (!relationship) throw new Error("Header/footer relationship missing.");
    const counterKey = `${role}:${referenceType}`;
    const occurrence = counters.get(counterKey) ?? 0;
    counters.set(counterKey, occurrence + 1);
    descriptors.push({
      partName: relationship.targetPartName,
      logicalRegionId: `${role}-${referenceType}-${occurrence}`,
      role,
    });
  }
  return descriptors.map((descriptor) => {
    const { partName } = descriptor;
    const entry = inspected.zip.entries.get(partName);
    if (!entry) throw new Error(`Missing structural part ${partName}.`);
    return {
      ...descriptor,
      part: indexBindingXmlPart(parseOrderedXml(entry.bytes, inspected.limits)),
    };
  });
}

function assertNoCustomXmlParts(bytes: Uint8Array): void {
  const inspected = inspectDocxPackage(bytes);
  if (
    [...inspected.zip.entries.keys()].some((partName) =>
      /^customXml(?:\/|$)/i.test(partName),
    )
  ) {
    throw new Error("Custom XML is not eligible for Office QA.");
  }
}

function wordOnOffEnabled(node: IndexedBindingNode): boolean {
  return parseWordOnOff(node);
}

function parseWordOnOff(node: IndexedBindingNode): boolean {
  return parseOnOffLexical(wordAttribute(node, "val"));
}

function parseOnOffLexical(value: string | undefined): boolean {
  if (value === undefined) return true;
  if (value === "1" || value === "true" || value === "on") return true;
  if (value === "0" || value === "false" || value === "off") return false;
  throw new Error("Invalid WordprocessingML on/off lexical value.");
}

function deriveOrdinaryOfficeContext(
  indexedPart: IndexedPackagePart,
  paragraph: IndexedBindingNode,
  field: TemplateField,
): NonNullable<OfficeCertifiedBindingExpectation["ordinaryOfficeContext"]> {
  const binding = field.rendererBinding.ordinaryPlaceholder;
  if (!binding || !isWordElement(paragraph, "p")) {
    throw new Error("Invalid ordinary-placeholder Office QA baseline.");
  }
  const strict = deriveOrdinaryPlaceholderBinding(
    indexedPart.part,
    paragraph,
    binding,
    "output",
  );
  if (!strict || strict.mutableValue.length === 0) {
    throw new Error("Ordinary-placeholder Office QA baseline is ambiguous.");
  }
  const visible = visibleParagraphText(indexedPart.part, paragraph);
  const start = visible.indexOf(strict.mutableValue);
  if (
    start < 0 ||
    visible.indexOf(strict.mutableValue, start + strict.mutableValue.length) >=
      0
  ) {
    throw new Error("Ordinary-placeholder Office QA baseline is ambiguous.");
  }
  const prefix = visible.slice(0, start);
  const suffix = visible.slice(start + strict.mutableValue.length);
  return Object.freeze({
    logicalRegionId: indexedPart.logicalRegionId,
    visiblePrefixLength: prefix.length,
    visibleSuffixLength: suffix.length,
    visiblePrefixSha256: canonicalSha256(prefix),
    visibleSuffixSha256: canonicalSha256(suffix),
    visibleStaticContextSha256: canonicalSha256({ prefix, suffix }),
  });
}

function readOrdinaryOfficeCandidate(
  indexedPart: IndexedPackagePart,
  paragraph: IndexedBindingNode,
  expected: OfficeExpectedFieldValue,
): OrdinaryOfficeCandidate | null {
  const context = expected.certifiedBinding.ordinaryOfficeContext;
  if (
    !context ||
    indexedPart.logicalRegionId !== context.logicalRegionId ||
    !isWordElement(paragraph, "p")
  ) {
    return null;
  }
  const visible = visibleParagraphText(indexedPart.part, paragraph);
  if (
    visible.length <
    context.visiblePrefixLength + context.visibleSuffixLength
  ) {
    return null;
  }
  const prefix = visible.slice(0, context.visiblePrefixLength);
  const suffix = context.visibleSuffixLength
    ? visible.slice(-context.visibleSuffixLength)
    : "";
  if (
    canonicalSha256(prefix) !== context.visiblePrefixSha256 ||
    canonicalSha256(suffix) !== context.visibleSuffixSha256 ||
    canonicalSha256({ prefix, suffix }) !== context.visibleStaticContextSha256
  ) {
    return null;
  }
  const value = visible.slice(
    context.visiblePrefixLength,
    context.visibleSuffixLength
      ? visible.length - context.visibleSuffixLength
      : visible.length,
  );
  return {
    value,
    prefix,
    suffix,
    identitySha256: canonicalSha256({
      qaVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
      bindingType: "ordinary_placeholder",
      controlKind: "ordinary_placeholder_text",
      logicalRegionId: indexedPart.logicalRegionId,
      tableLocation: deriveTableLocation(indexedPart.part, paragraph),
      visiblePrefixSha256: canonicalSha256(prefix),
      visibleSuffixSha256: canonicalSha256(suffix),
      visibleStaticContextSha256: canonicalSha256({ prefix, suffix }),
    }),
  };
}

function locateAtCertifiedRendererPath(
  parts: readonly IndexedPackagePart[],
  field: TemplateField,
): LocatedField {
  const indexedPart = parts.find(
    (candidate) => candidate.partName === field.rendererBinding.partName,
  );
  const node = indexedPart?.part.byCanonicalPath.get(
    field.rendererBinding.canonicalPath,
  );
  if (!indexedPart || !node) {
    throw new Error(`Certified renderer path missing for ${field.fieldId}.`);
  }
  const bindingType = supportedBindingType(field.rendererBinding.bindingType);
  const identity = deriveOoxmlBindingIdentity(
    indexedPart.part,
    node,
    bindingType,
    field.rendererBinding.ordinaryPlaceholder,
    "output",
  );
  if (!identity) throw new Error(`Invalid renderer binding ${field.fieldId}.`);
  const controlKind =
    bindingType === "ordinary_placeholder"
      ? "ordinary_placeholder_text"
      : controlKindFor(indexedPart.part, node, field.kind);
  return {
    expected: {
      fieldId: field.fieldId,
      semanticKind: field.kind,
      controlKind,
      expectedValueSha256: "",
      rendererObservedValueSha256: "",
      expectedControlStateSha256: "",
      rendererControlSerializationSha256: "",
      expectedOccurrences: 1,
      expectedDisposition: "rendered",
      certifiedBinding: certifiedExpectation(field, controlKind, {
        indexedPart,
        node,
      }),
    },
    indexedPart,
    node,
    bindingIdentitySha256: identity.identitySha256,
    nativeIdentity: identity.nativeIdentity,
    tableLocation: deriveTableLocation(indexedPart.part, node),
    actualOccurrences: 1,
    ordinal: field.rendererBinding.ordinal,
  };
}

function locateLogicalOutputBindings(
  parts: readonly IndexedPackagePart[],
  expected: OfficeExpectedFieldValue,
): Omit<LocatedField, "ordinal">[] {
  const binding = expected.certifiedBinding;
  const matches: Omit<LocatedField, "ordinal">[] = [];
  if (binding.bindingType === "ordinary_placeholder") {
    for (const indexedPart of parts) {
      for (const node of indexedPart.part.nodes) {
        if (!isWordElement(node, "p")) continue;
        const candidate = readOrdinaryOfficeCandidate(
          indexedPart,
          node,
          expected,
        );
        if (!candidate) continue;
        const tableLocation = deriveTableLocation(indexedPart.part, node);
        if (
          canonicalSha256(tableLocation) !==
          canonicalSha256(binding.tableLocation)
        ) {
          continue;
        }
        const valueMatches =
          expected.expectedDisposition === "rendered"
            ? hashOfficeQaSemanticValue(expected.fieldId, candidate.value) ===
              expected.expectedValueSha256
            : Boolean(
                binding.ordinaryPlaceholder &&
                candidate.value.length ===
                  binding.ordinaryPlaceholder.tokenTextLength &&
                canonicalSha256(candidate.value) ===
                  binding.ordinaryPlaceholder.tokenTextSha256,
              );
        if (!valueMatches) continue;
        const strictIdentity =
          indexedPart.partName === binding.partName &&
          node.canonicalPath === binding.canonicalPath &&
          binding.ordinaryPlaceholder
            ? deriveOoxmlBindingIdentity(
                indexedPart.part,
                node,
                "ordinary_placeholder",
                binding.ordinaryPlaceholder,
                "output",
              )
            : null;
        matches.push({
          expected,
          indexedPart,
          node,
          bindingIdentitySha256:
            strictIdentity?.identitySha256 ?? candidate.identitySha256,
          nativeIdentity: {
            sdtId: null,
            tag: null,
            alias: null,
            legacyName: null,
          },
          tableLocation,
          actualOccurrences: 0,
          ordinaryOfficeCandidate: candidate,
        });
      }
    }
    const occurrences = matches.length;
    return matches.map((match) => ({
      ...match,
      actualOccurrences: occurrences,
    }));
  }
  for (const indexedPart of parts) {
    for (const node of indexedPart.part.nodes) {
      const identity = deriveOoxmlBindingIdentity(
        indexedPart.part,
        node,
        binding.bindingType,
      );
      if (!identity) continue;
      const tableLocation = deriveTableLocation(indexedPart.part, node);
      let controlKind: OfficeQaControlKind;
      try {
        controlKind = controlKindFor(
          indexedPart.part,
          node,
          expected.semanticKind as TemplateField["kind"],
        );
      } catch {
        continue;
      }
      const locator = logicalFieldLocatorSha256({
        fieldId: expected.fieldId,
        bindingType: binding.bindingType,
        nativeIdentity: identity.nativeIdentity,
        controlKind,
        tableLocation,
        labelContextSha256: binding.labelContextSha256,
      });
      if (locator !== binding.logicalFieldLocatorSha256) continue;
      matches.push({
        expected,
        indexedPart,
        node,
        bindingIdentitySha256: identity.identitySha256,
        nativeIdentity: identity.nativeIdentity,
        tableLocation,
        actualOccurrences: 0,
      });
    }
  }
  const occurrences = matches.length;
  return matches.map((match) => ({ ...match, actualOccurrences: occurrences }));
}

function censusNativeLogicalLocators(
  parts: readonly IndexedPackagePart[],
  fields: readonly OfficeExpectedFieldValue[],
): string[] {
  const output: string[] = [];
  for (const part of parts) {
    for (const node of part.part.nodes) {
      for (const bindingType of [
        "content_control",
        "legacy_form_field",
      ] as const) {
        const identity = deriveOoxmlBindingIdentity(
          part.part,
          node,
          bindingType,
        );
        if (!identity) continue;
        const tableLocation = deriveTableLocation(part.part, node);
        const matches = fields.filter((field) => {
          if (field.certifiedBinding.bindingType !== bindingType) return false;
          let controlKind: OfficeQaControlKind;
          try {
            controlKind = controlKindFor(
              part.part,
              node,
              field.semanticKind as TemplateField["kind"],
            );
          } catch {
            return false;
          }
          return (
            logicalFieldLocatorSha256({
              fieldId: field.fieldId,
              bindingType,
              nativeIdentity: identity.nativeIdentity,
              controlKind,
              tableLocation,
              labelContextSha256: field.certifiedBinding.labelContextSha256,
            }) === field.certifiedBinding.logicalFieldLocatorSha256
          );
        });
        if (matches.length === 1) {
          output.push(matches[0]!.certifiedBinding.logicalFieldLocatorSha256);
        } else {
          output.push(
            canonicalSha256({
              qaVersion: OFFICE_DOCX_BYTE_READBACK_QA_VERSION,
              partName: part.partName,
              bindingType,
              nativeIdentity: identity.nativeIdentity,
              controlKind: matches.length === 0 ? "unmatched" : "ambiguous",
              tableLocation,
            }),
          );
        }
      }
    }
  }
  return output;
}

function valueForDisposition(
  value: unknown,
  disposition: OfficeExpectedFieldValue["expectedDisposition"],
): unknown {
  return disposition === "rendered" ? value : null;
}

function expectedFieldShape(expected: OfficeExpectedFieldValue): TemplateField {
  return {
    fieldId: expected.fieldId,
    kind: expected.semanticKind as TemplateField["kind"],
    originalLabel: "Synthetic QA field",
    labelSource: "generated",
    displayOrder: 0,
    detectionStatus: "recognized",
    allowedOptions: [],
    rendererBinding: {
      partName: expected.certifiedBinding.partName,
      bindingType: expected.certifiedBinding.bindingType,
      ...(expected.certifiedBinding.bindingProfile === undefined
        ? {}
        : { bindingProfile: expected.certifiedBinding.bindingProfile }),
      ...(expected.certifiedBinding.ordinaryPlaceholder === undefined
        ? {}
        : {
            ordinaryPlaceholder: expected.certifiedBinding.ordinaryPlaceholder,
          }),
      path: expected.certifiedBinding.canonicalPath,
      canonicalPath: expected.certifiedBinding.canonicalPath,
      ordinal: expected.certifiedBinding.ordinal,
      ...expected.certifiedBinding.nativeIdentity,
      tableIndex: expected.certifiedBinding.tableLocation.tableIndex,
      rowIndex: expected.certifiedBinding.tableLocation.rowIndex,
      cellIndex: expected.certifiedBinding.tableLocation.cellIndex,
      repeatAncestorPath: null,
      canonicalRepeatAncestorPath:
        expected.certifiedBinding.canonicalRepeatAncestorPath,
      sourceControlSha256: expected.certifiedBinding.sourceControlSha256,
      sourceBindingIdentitySha256:
        expected.certifiedBinding.sourceBindingIdentitySha256,
      certifiedBindingSha256: expected.certifiedBinding.certifiedBindingSha256,
      originalContentSha256: expected.certifiedBinding.sourceControlSha256,
    },
    required: false,
    unknownPolicy: "blank",
    clinicallyMaterial: false,
    criticality: "routine",
    tableId: null,
    rowPrototype: false,
  };
}

function readLocatedValue(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  field: Pick<TemplateField, "fieldId" | "kind" | "rendererBinding">,
): {
  controlKind: OfficeQaControlKind;
  value: unknown;
  controlState: unknown;
  rawSerializationSha256: string;
  officeCalculatedPresentation?: Exclude<OfficeCalculatedPresentation, "none">;
  behaviorNormalizations?: readonly (
    | "calendar_omitted_defaults_gregorian"
    | "store_mapped_data_as_not_applicable_unbound"
  )[];
} {
  const bindingType = field.rendererBinding.bindingType;
  if (bindingType === "ordinary_placeholder") {
    const binding = field.rendererBinding.ordinaryPlaceholder;
    if (!binding || !isWordElement(node, "p")) {
      throw new Error("Malformed ordinary-placeholder binding.");
    }
    const derived = deriveOrdinaryPlaceholderBinding(
      part,
      node,
      binding,
      "output",
    );
    if (!derived) {
      throw new Error("Ordinary-placeholder output binding is invalid.");
    }
    const visible = visibleParagraphText(part, node);
    const start = visible.indexOf(derived.mutableValue);
    if (
      start < 0 ||
      visible.indexOf(
        derived.mutableValue,
        start + derived.mutableValue.length,
      ) >= 0
    ) {
      throw new Error("Ordinary-placeholder output value is ambiguous.");
    }
    const prefix = visible.slice(0, start);
    const suffix = visible.slice(start + derived.mutableValue.length);
    return {
      controlKind: "ordinary_placeholder_text",
      value: derived.mutableValue,
      controlState: ordinaryOfficeControlState(prefix, suffix),
      rawSerializationSha256: canonicalSha256(node.node),
    };
  }
  if (bindingType === "content_control") {
    const properties = directWordChild(part, node, "sdtPr");
    const content = directWordChild(part, node, "sdtContent");
    if (!properties || !content) throw new Error("Malformed content control.");
    const placeholderShown =
      descendantsWord(part, properties, "showingPlcHdr").length > 0;
    const placeholderStylePresent = descendantsWord(
      part,
      content,
      "rStyle",
    ).some((style) => wordAttribute(style, "val") === "PlaceholderText");
    const controlKind = controlKindFor(part, node, field.kind);
    if (controlKind === "checkbox_content_control") {
      const checkboxes = descendantsLocal(part, properties, "checkbox").filter(
        (candidate) =>
          candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
      );
      if (checkboxes.length !== 1)
        throw new Error("Invalid checkbox definition.");
      const checkbox = checkboxes[0]!;
      const checkedNodes = descendantsLocal(part, checkbox, "checked").filter(
        (candidate) =>
          candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
      );
      if (checkedNodes.length !== 1) throw new Error("Invalid checkbox state.");
      const checked = checkedNodes[0]!;
      const raw = namespacedAttribute(
        checked,
        WORDPROCESSINGML_2010_NAMESPACE,
        "val",
      );
      const value = parseOnOffLexical(raw);
      const checkedStates = descendantsLocal(
        part,
        checkbox,
        "checkedState",
      ).filter(
        (candidate) =>
          candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
      );
      const uncheckedStates = descendantsLocal(
        part,
        checkbox,
        "uncheckedState",
      ).filter(
        (candidate) =>
          candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
      );
      if (checkedStates.length !== 1 || uncheckedStates.length !== 1) {
        throw new Error("Checkbox codepoint definition missing.");
      }
      const checkedState = checkedStates[0]!;
      const uncheckedState = uncheckedStates[0]!;
      const state = value ? checkedState : uncheckedState;
      const glyphCode = namespacedAttribute(
        state,
        WORDPROCESSINGML_2010_NAMESPACE,
        "val",
      );
      const displayed = wordText(part, content);
      const checkedCodePoint = namespacedAttribute(
        checkedState,
        WORDPROCESSINGML_2010_NAMESPACE,
        "val",
      );
      const uncheckedCodePoint = namespacedAttribute(
        uncheckedState,
        WORDPROCESSINGML_2010_NAMESPACE,
        "val",
      );
      if (
        !checkedCodePoint ||
        !uncheckedCodePoint ||
        !/^[a-f0-9]{1,6}$/i.test(checkedCodePoint) ||
        !/^[a-f0-9]{1,6}$/i.test(uncheckedCodePoint)
      ) {
        throw new Error("Checkbox codepoint definition missing.");
      }
      const expectedGlyph =
        glyphCode && /^[a-f0-9]{1,6}$/i.test(glyphCode)
          ? String.fromCodePoint(Number.parseInt(glyphCode, 16))
          : value
            ? "☒"
            : "☐";
      if (displayed !== expectedGlyph)
        throw new Error("Checkbox glyph mismatch.");
      return {
        controlKind,
        value,
        controlState: {
          checked: value,
          visibleGlyphState: value ? "checked" : "unchecked",
          checkedCodePoint: checkedCodePoint.toUpperCase(),
          uncheckedCodePoint: uncheckedCodePoint.toUpperCase(),
          placeholderShown,
          placeholderStylePresent,
        },
        rawSerializationSha256: canonicalSha256(node.node),
      };
    }
    if (controlKind === "date_content_control") {
      const dates = directWordChildren(part, properties, "date");
      if (dates.length !== 1) throw new Error("Invalid date control.");
      const date = dates[0]!;
      const fullDate = wordAttribute(date, "fullDate");
      const match = /^(\d{4}-\d{2}-\d{2})(?:T|$)/.exec(fullDate ?? "");
      if (!match) throw new Error("Date control lacks ISO fullDate.");
      const dateFormats = descendantsWord(part, date, "dateFormat");
      const locales = descendantsWord(part, date, "lid");
      const calendars = descendantsWord(part, date, "calendar");
      const mappedDataKinds = descendantsWord(part, date, "storeMappedDataAs");
      const dataBindings = descendantsWord(part, properties, "dataBinding");
      if (
        dateFormats.length !== 1 ||
        locales.length !== 1 ||
        calendars.length > 1 ||
        mappedDataKinds.length > 1 ||
        dataBindings.length > 0
      ) {
        throw new Error("Date behavior definition missing.");
      }
      const dateFormat = wordAttribute(dateFormats[0], "val");
      const locale = wordAttribute(locales[0], "val");
      const explicitCalendar = wordAttribute(calendars[0], "val");
      const explicitStoreMappedDataAs = wordAttribute(
        mappedDataKinds[0],
        "val",
      );
      if (
        !dateFormat ||
        !locale ||
        (calendars.length === 1 && !explicitCalendar) ||
        (mappedDataKinds.length === 1 && !explicitStoreMappedDataAs)
      ) {
        throw new Error("Date behavior definition missing.");
      }
      const behaviorNormalizations = [
        "store_mapped_data_as_not_applicable_unbound" as const,
        ...(calendars.length === 0
          ? (["calendar_omitted_defaults_gregorian"] as const)
          : []),
      ];
      return {
        controlKind,
        value: match[1],
        controlState: {
          isoDate: match[1],
          dateFormat,
          locale,
          calendar: explicitCalendar ?? "gregorian",
          storeMappedDataAs: "not_applicable_unbound",
          displayedTextSha256: canonicalSha256(wordText(part, content)),
          placeholderShown,
          placeholderStylePresent,
        },
        rawSerializationSha256: canonicalSha256(node.node),
        behaviorNormalizations,
      };
    }
    if (
      controlKind === "dropdown_content_control" ||
      controlKind === "combo_box_content_control"
    ) {
      const choice = directWordChild(
        part,
        properties,
        controlKind === "dropdown_content_control"
          ? "dropDownList"
          : "comboBox",
      );
      const choiceCount = directWordChildren(
        part,
        properties,
        controlKind === "dropdown_content_control"
          ? "dropDownList"
          : "comboBox",
      ).length;
      if (!choice || choiceCount !== 1) {
        throw new Error("Invalid select control definition.");
      }
      const displayed = wordText(part, content);
      const options = choice
        ? descendantsWord(part, choice, "listItem").filter(
            (item) => wordAttribute(item, "displayText") === displayed,
          )
        : [];
      if (options.length !== 1)
        throw new Error("Select value is not an exact option.");
      const option = options[0]!;
      const value = wordAttribute(option, "value");
      if (value === undefined) throw new Error("Select option lacks value.");
      const allOptions = descendantsWord(part, choice, "listItem");
      const orderedOptions = allOptions.map((candidate, ordinal) => ({
        ordinal,
        displayText: wordAttribute(candidate, "displayText") ?? null,
        value: wordAttribute(candidate, "value") ?? null,
      }));
      if (
        orderedOptions.some(
          (candidate) =>
            candidate.displayText === null || candidate.value === null,
        )
      ) {
        throw new Error("Select option definition is incomplete.");
      }
      return {
        controlKind,
        value,
        controlState: {
          selectedOptionOrdinal: allOptions.indexOf(option),
          displayedTextSha256: canonicalSha256(displayed),
          optionValueSha256: canonicalSha256(value),
          orderedOptionsSha256: canonicalSha256(orderedOptions),
          placeholderShown,
          placeholderStylePresent,
        },
        rawSerializationSha256: canonicalSha256(node.node),
      };
    }
    const textDefinitions = directWordChildren(part, properties, "text");
    if (textDefinitions.length !== 1) {
      throw new Error("Invalid text control definition.");
    }
    const multiLineRaw = wordAttribute(textDefinitions[0], "multiLine");
    const multiLine =
      multiLineRaw === undefined ? false : parseOnOffLexical(multiLineRaw);
    return {
      controlKind,
      value: wordText(part, content),
      controlState: {
        placeholderShown,
        placeholderStylePresent,
        multiLine,
      },
      rawSerializationSha256: canonicalSha256(node.node),
    };
  }

  if (bindingType === "legacy_form_field") {
    const formData = descendantsWord(part, node, "ffData")[0];
    if (!formData) throw new Error("Malformed legacy field.");
    const resultText = legacyResultText(part, node);
    const checkboxes = descendantsWord(part, formData, "checkBox");
    if (checkboxes.length > 1)
      throw new Error("Invalid legacy checkbox definition.");
    const checkbox = checkboxes[0];
    if (checkbox) {
      const checkedNodes = descendantsWord(part, checkbox, "checked");
      const defaultNodes = descendantsWord(part, checkbox, "default");
      if (checkedNodes.length > 1 || defaultNodes.length > 1) {
        throw new Error("Invalid legacy checkbox state.");
      }
      const checkedNode = checkedNodes[0];
      const defaultNode = defaultNodes[0];
      const value = checkedNode
        ? parseWordOnOff(checkedNode)
        : defaultNode
          ? parseWordOnOff(defaultNode)
          : (() => {
              throw new Error(
                "Legacy checkbox lacks checked state and explicit default.",
              );
            })();
      const paragraphGlyph = legacyCheckboxGlyph(part, node);
      if (paragraphGlyph !== (value ? "☒" : "☐")) {
        throw new Error("Legacy checkbox glyph mismatch.");
      }
      return {
        controlKind: "legacy_checkbox",
        value,
        controlState: {
          checked: value,
          visibleGlyphState: value ? "checked" : "unchecked",
        },
        rawSerializationSha256: canonicalSha256(
          legacyProofContainer(node).node,
        ),
      };
    }
    const dropdowns = descendantsWord(part, formData, "ddList");
    if (dropdowns.length > 1)
      throw new Error("Invalid legacy dropdown definition.");
    const dropdown = dropdowns[0];
    if (dropdown) {
      const resultNodes = descendantsWord(part, dropdown, "result");
      if (resultNodes.length !== 1) {
        throw new Error("Invalid legacy dropdown ordinal.");
      }
      const result = wordAttribute(resultNodes[0], "val");
      if (!result || !/^(?:0|[1-9][0-9]*)$/.test(result)) {
        throw new Error("Invalid legacy dropdown ordinal.");
      }
      const entries = descendantsWord(part, dropdown, "listEntry");
      const orderedEntries = entries.map((entry, ordinal) => ({
        ordinal,
        value: wordAttribute(entry, "val") ?? null,
      }));
      if (orderedEntries.some((entry) => entry.value === null)) {
        throw new Error("Legacy dropdown entry is incomplete.");
      }
      const option = entries[Number(result)];
      const value = option ? wordAttribute(option, "val") : undefined;
      if (value === undefined) {
        throw new Error("Legacy dropdown result mismatch.");
      }
      const officeCalculatedPresentation =
        resultText === value
          ? undefined
          : legacyDropdownPresentationIsProven(part, node, formData, resultText)
            ? ("libreoffice_legacy_dropdown" as const)
            : null;
      if (officeCalculatedPresentation === null) {
        throw new Error("Legacy dropdown result mismatch.");
      }
      return {
        controlKind: "legacy_dropdown",
        value,
        controlState: {
          selectedOptionOrdinal: Number(result),
          selectedValueSha256: canonicalSha256(value),
          orderedEntriesSha256: canonicalSha256(orderedEntries),
          nativeValuePresentationContract:
            "legacy-dropdown-native-presentation/1.0.0",
        },
        rawSerializationSha256: canonicalSha256(
          legacyProofContainer(node).node,
        ),
        officeCalculatedPresentation,
      };
    }
    const textInput = descendantsWord(part, formData, "textInput")[0];
    if (!textInput) throw new Error("Unsupported legacy field.");
    const defaultValue = wordAttribute(
      descendantsWord(part, textInput, "default")[0],
      "val",
    );
    const value = defaultValue ?? resultText;
    const typeNodes = descendantsWord(part, textInput, "type");
    const maxLengthNodes = descendantsWord(part, textInput, "maxLength");
    if (typeNodes.length > 1 || maxLengthNodes.length > 1) {
      throw new Error("Invalid legacy text behavior definition.");
    }
    const type = wordAttribute(typeNodes[0], "val") ?? "regular";
    const maxLengthRaw = wordAttribute(maxLengthNodes[0], "val");
    if (
      maxLengthRaw !== undefined &&
      (!/^[1-9][0-9]*$/.test(maxLengthRaw) || Number(maxLengthRaw) > 32767)
    ) {
      throw new Error("Invalid legacy text maximum length.");
    }
    const format = wordAttribute(
      descendantsWord(part, textInput, "format")[0],
      "val",
    );
    return {
      controlKind: type === "date" ? "legacy_date" : "legacy_text",
      value,
      controlState: {
        defaultValueSha256: canonicalSha256(value),
        resultTextSha256: canonicalSha256(resultText),
        legacyDateFormat: type === "date" ? (format ?? null) : null,
        legacyTextType: type,
        maxLength: maxLengthRaw === undefined ? null : Number(maxLengthRaw),
      },
      rawSerializationSha256: canonicalSha256(legacyProofContainer(node).node),
    };
  }

  if (bindingType === "table_cell") {
    const contentNodes = visibleTableCellContentNodes(part, node);
    return {
      controlKind: "fixed_table_cell",
      value: wordTextFromNodes(contentNodes),
      controlState: {
        tableLocation: deriveTableLocation(part, node),
        paragraphCount: descendantsWord(part, node, "p").length,
        contentTabCount: contentNodes.filter(
          (candidate) => candidate.visit.localName === "tab",
        ).length,
        breakCount: contentNodes.filter((candidate) =>
          ["br", "cr"].includes(candidate.visit.localName),
        ).length,
      },
      rawSerializationSha256: canonicalSha256(node.node),
    };
  }
  throw new Error("Unsupported Office QA binding.");
}

function readOrdinaryOfficeLocatedValue(
  record: LocatedField,
): ReturnType<typeof readLocatedValue> {
  const candidate = record.ordinaryOfficeCandidate;
  if (!candidate) {
    throw new Error("Ordinary-placeholder Office candidate is missing.");
  }
  return {
    controlKind: "ordinary_placeholder_text",
    value: candidate.value,
    controlState: ordinaryOfficeControlState(
      candidate.prefix,
      candidate.suffix,
    ),
    rawSerializationSha256: canonicalSha256(record.node.node),
  };
}

function ordinaryOfficeControlState(prefix: string, suffix: string): unknown {
  return {
    bindingProfile: "ORDINARY_PLACEHOLDER_TOKEN_V1",
    visiblePrefixSha256: canonicalSha256(prefix),
    visibleSuffixSha256: canonicalSha256(suffix),
    visibleStaticContextSha256: canonicalSha256({ prefix, suffix }),
  };
}

/**
 * LibreOffice 25.8 removes the cached dropdown result text and emits a
 * deterministic native-form-field bookmark representation. Accept that
 * completed-byte representation only when the field instruction, empty result
 * region, bookmark names/IDs, and exact structural sequence agree. Merely
 * deleting w:t or retaining w:result metadata is insufficient. The round-trip
 * verifier separately requires pinned, exact PDF visual survival before this
 * representation may pass the QA-only gate.
 */
function legacyDropdownPresentationIsProven(
  part: IndexedBindingPart,
  begin: IndexedBindingNode,
  formData: IndexedBindingNode,
  resultText: string,
): boolean {
  if (resultText !== "") return false;

  const nameNodes = descendantsWord(part, formData, "name");
  if (nameNodes.length !== 1) return false;
  const legacyName = wordAttribute(nameNodes[0], "val");
  if (!legacyName || !/^[A-Za-z][A-Za-z0-9 ]{0,39}$/.test(legacyName)) {
    return false;
  }
  const expectedBookmarkName = legacyName.replaceAll(" ", "_");
  const paragraph = legacyProofContainer(begin);
  const nodes = [paragraph, ...descendantsLocal(part, paragraph, "")];
  const startIndex = nodes.findIndex((candidate) => candidate === begin);
  if (startIndex < 0) return false;

  let depth = 0;
  let separateIndex = -1;
  let endIndex = -1;
  const instruction: string[] = [];
  for (let index = startIndex; index < nodes.length; index += 1) {
    const candidate = nodes[index]!;
    if (isWordElement(candidate, "fldChar")) {
      const type = wordAttribute(candidate, "fldCharType");
      if (type === "begin") depth += 1;
      else if (type === "separate" && depth === 1) separateIndex = index;
      else if (type === "end") {
        depth -= 1;
        if (depth === 0) {
          endIndex = index;
          break;
        }
      }
    } else if (
      depth === 1 &&
      separateIndex < 0 &&
      isWordElement(candidate, "instrText")
    ) {
      instruction.push(nodeText(candidate.node));
    }
  }
  if (
    instruction.join("").trim().toUpperCase() !== "FORMDROPDOWN" ||
    separateIndex < 0 ||
    endIndex <= separateIndex
  ) {
    return false;
  }

  const resultRegion = nodes.slice(separateIndex + 1, endIndex);
  if (
    resultRegion.some(
      (candidate) =>
        candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
        !["bookmarkStart", "bookmarkEnd", "r", "rPr"].includes(
          candidate.visit.localName,
        ),
    )
  ) {
    return false;
  }
  const starts = resultRegion.filter((candidate) =>
    isWordElement(candidate, "bookmarkStart"),
  );
  const ends = resultRegion.filter((candidate) =>
    isWordElement(candidate, "bookmarkEnd"),
  );
  if (starts.length !== 2 || ends.length !== 1) return false;
  const startIds = starts.map((candidate) => wordAttribute(candidate, "id"));
  const startNames = starts.map((candidate) =>
    wordAttribute(candidate, "name"),
  );
  const endId = wordAttribute(ends[0], "id");
  return Boolean(
    startIds.every((id) => id && /^(?:0|[1-9][0-9]*)$/.test(id)) &&
    startIds[0] !== startIds[1] &&
    startNames.every((name) => name === expectedBookmarkName) &&
    endId === startIds[1] &&
    !resultRegion.some((candidate) => isWordElement(candidate, "t")),
  );
}

function controlKindFor(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  fieldKind: TemplateField["kind"],
): OfficeQaControlKind {
  const identityContent = isWordElement(node, "sdt");
  if (!identityContent) {
    if (isWordElement(node, "tc")) return "fixed_table_cell";
    const formData = descendantsWord(part, node, "ffData")[0];
    if (!formData) throw new Error("Unsupported Office field binding.");
    if (descendantsWord(part, formData, "checkBox").length > 0) {
      return "legacy_checkbox";
    }
    if (descendantsWord(part, formData, "ddList").length > 0) {
      return "legacy_dropdown";
    }
    const textInput = descendantsWord(part, formData, "textInput")[0];
    const type = textInput
      ? wordAttribute(descendantsWord(part, textInput, "type")[0], "val")
      : undefined;
    return type === "date" || fieldKind === "date"
      ? "legacy_date"
      : "legacy_text";
  }
  const properties = directWordChild(part, node, "sdtPr");
  if (!properties) throw new Error("Content control properties missing.");
  if (
    descendantsLocal(part, properties, "checkbox").some(
      (candidate) =>
        candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
    )
  ) {
    return "checkbox_content_control";
  }
  if (directWordChild(part, properties, "date")) return "date_content_control";
  if (directWordChild(part, properties, "dropDownList")) {
    return "dropdown_content_control";
  }
  if (directWordChild(part, properties, "comboBox")) {
    return "combo_box_content_control";
  }
  if (directWordChild(part, properties, "text")) {
    return "text_content_control";
  }
  throw new Error(
    "Rich or unknown content controls are not Office-QA eligible.",
  );
}

function directWordChild(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode | undefined {
  return directWordChildren(part, node, localName)[0];
}

function directWordChildren(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  return childrenOf(node.node)
    .map((child) => part.byNode.get(child))
    .filter((candidate): candidate is IndexedBindingNode =>
      Boolean(candidate && isWordElement(candidate, localName)),
    );
}

function descendantsWord(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  return descendantsLocal(part, node, localName).filter(
    (candidate) => candidate.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE,
  );
}

function descendantsLocal(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  const output: IndexedBindingNode[] = [];
  const stack = [...childrenOf(node.node)].reverse();
  while (stack.length > 0) {
    const child = stack.pop()!;
    if (tagOf(child) === "#text" || tagOf(child) === "?xml") continue;
    const indexed = part.byNode.get(child);
    if (!indexed) throw new Error("Malformed indexed XML part.");
    if (!localName || indexed.visit.localName === localName)
      output.push(indexed);
    const grandchildren = childrenOf(child);
    for (let index = grandchildren.length - 1; index >= 0; index -= 1) {
      stack.push(grandchildren[index]!);
    }
  }
  return output;
}

function isWordElement(node: IndexedBindingNode, localName: string): boolean {
  return (
    node.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    node.visit.localName === localName
  );
}

function wordAttribute(
  node: IndexedBindingNode | undefined,
  localName: string,
): string | undefined {
  return node
    ? exactExpandedAttribute(node.visit, WORDPROCESSINGML_NAMESPACE, localName)
    : undefined;
}

function namespacedAttribute(
  node: IndexedBindingNode | undefined,
  namespaceUri: string,
  localName: string,
): string | undefined {
  return node
    ? exactExpandedAttribute(node.visit, namespaceUri, localName)
    : undefined;
}

function wordText(part: IndexedBindingPart, node: IndexedBindingNode): string {
  return wordTextFromNodes([node, ...descendantsLocal(part, node, "")]);
}

/**
 * Returns physician-visible text in one paragraph while excluding formatting,
 * field instructions, tracked-deleted content, and non-Word namespaces.
 * Ordinary-placeholder certification already rejects those structures; this
 * second filter keeps Office QA from treating hidden/properties text as proof.
 */
function visibleParagraphText(
  part: IndexedBindingPart,
  paragraph: IndexedBindingNode,
): string {
  if (!isWordElement(paragraph, "p")) {
    throw new Error("Visible paragraph readback requires w:p.");
  }
  const nodes = [paragraph, ...descendantsLocal(part, paragraph, "")].filter(
    (candidate) => {
      if (candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) {
        return false;
      }
      let ancestor = candidate.parent;
      while (ancestor && ancestor !== paragraph) {
        if (
          ancestor.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          ["pPr", "rPr", "del", "moveFrom", "instrText", "fldSimple"].includes(
            ancestor.visit.localName,
          )
        ) {
          return false;
        }
        ancestor = ancestor.parent;
      }
      return !["delText", "instrText"].includes(candidate.visit.localName);
    },
  );
  return wordTextFromNodes(nodes);
}

/**
 * Returns only visible table-cell content. Word stores paragraph tab-stop
 * definitions as `w:pPr/w:tabs/w:tab`; those nodes affect layout but are not a
 * literal tab in the physician-visible field value. Content-level `w:tab`
 * nodes remain visible and are deliberately retained.
 */
function visibleTableCellContentNodes(
  part: IndexedBindingPart,
  cell: IndexedBindingNode,
): IndexedBindingNode[] {
  return [cell, ...descendantsLocal(part, cell, "")].filter((candidate) => {
    if (candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) {
      return false;
    }
    let ancestor = candidate.parent;
    while (ancestor && ancestor !== cell) {
      if (
        ancestor.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        ["pPr", "rPr", "tcPr", "trPr", "tblPr"].includes(
          ancestor.visit.localName,
        )
      ) {
        return false;
      }
      ancestor = ancestor.parent;
    }
    return true;
  });
}

function wordTextFromNodes(nodes: readonly IndexedBindingNode[]): string {
  const output: string[] = [];
  for (const candidate of nodes) {
    if (candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
    if (candidate.visit.localName === "t")
      output.push(nodeText(candidate.node));
    else if (candidate.visit.localName === "tab") output.push("\t");
    else if (
      candidate.visit.localName === "br" ||
      candidate.visit.localName === "cr"
    ) {
      output.push("\n");
    }
  }
  return output.join("");
}

function maskedVisibleNodes(
  part: IndexedBindingPart,
  located: readonly Omit<LocatedField, "ordinal">[],
): Set<IndexedBindingNode> {
  const masked = new Set<IndexedBindingNode>();
  const maskTree = (root: IndexedBindingNode): void => {
    masked.add(root);
    for (const candidate of descendantsLocal(part, root, "")) {
      masked.add(candidate);
    }
  };
  for (const field of located) {
    if (field.expected.certifiedBinding.bindingType !== "legacy_form_field") {
      maskTree(field.node);
      continue;
    }
    const paragraph = legacyProofContainer(field.node);
    const paragraphNodes = [
      paragraph,
      ...descendantsLocal(part, paragraph, ""),
    ];
    const start = paragraphNodes.findIndex(
      (candidate) => candidate === field.node,
    );
    if (start < 0) throw new Error("Legacy field mask start missing.");
    let depth = 0;
    let ended = false;
    for (const candidate of paragraphNodes.slice(start)) {
      masked.add(candidate);
      if (!isWordElement(candidate, "fldChar")) continue;
      const fieldType = wordAttribute(candidate, "fldCharType");
      if (fieldType === "begin") depth += 1;
      else if (fieldType === "end") {
        depth -= 1;
        if (depth === 0) {
          ended = true;
          break;
        }
      }
    }
    if (!ended) throw new Error("Legacy field mask end missing.");
    if (field.expected.controlKind === "legacy_checkbox") {
      for (const candidate of paragraphNodes) {
        if (
          isWordElement(candidate, "t") &&
          ["☒", "☐"].includes(nodeText(candidate.node))
        ) {
          masked.add(candidate);
        }
      }
    }
  }
  maskCalculatedWordFieldResults(part, masked);
  return masked;
}

function maskCalculatedWordFieldResults(
  part: IndexedBindingPart,
  masked: Set<IndexedBindingNode>,
): void {
  const harmless = new Set([
    "DATE",
    "TIME",
    "PAGE",
    "NUMPAGES",
    "SECTION",
    "SECTIONPAGES",
  ]);
  for (const simple of part.nodes.filter((node) =>
    isWordElement(node, "fldSimple"),
  )) {
    const instruction = wordAttribute(simple, "instr")
      ?.trim()
      .split(/\s+/)[0]
      ?.toUpperCase();
    if (!instruction || !harmless.has(instruction)) continue;
    for (const candidate of descendantsWord(part, simple, "t"))
      masked.add(candidate);
  }
  for (const begin of part.nodes.filter(
    (node) =>
      isWordElement(node, "fldChar") &&
      wordAttribute(node, "fldCharType") === "begin",
  )) {
    const paragraph = legacyProofContainer(begin);
    const nodes = [paragraph, ...descendantsLocal(part, paragraph, "")];
    const start = nodes.findIndex((candidate) => candidate === begin);
    if (start < 0) continue;
    let depth = 0;
    let inResult = false;
    const instructionText: string[] = [];
    const resultTextNodes: IndexedBindingNode[] = [];
    for (const candidate of nodes.slice(start)) {
      if (isWordElement(candidate, "fldChar")) {
        const type = wordAttribute(candidate, "fldCharType");
        if (type === "begin") depth += 1;
        else if (type === "separate" && depth === 1) inResult = true;
        else if (type === "end") {
          depth -= 1;
          if (depth === 0) break;
        }
        continue;
      }
      if (depth !== 1) continue;
      if (!inResult && isWordElement(candidate, "instrText")) {
        instructionText.push(nodeText(candidate.node));
      } else if (inResult && isWordElement(candidate, "t")) {
        resultTextNodes.push(candidate);
      }
    }
    const instruction = instructionText
      .join("")
      .trim()
      .split(/\s+/)[0]
      ?.toUpperCase();
    if (!instruction || !harmless.has(instruction)) continue;
    for (const candidate of resultTextNodes) masked.add(candidate);
  }
}

function normalizedStaticStructureToken(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
): string | null {
  if (node.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) return null;
  const local = node.visit.localName;
  if (
    ["document", "body", "hdr", "ftr", "p", "tblGrid", "gridCol"].includes(
      local,
    )
  ) {
    return local;
  }
  if (local === "tbl" || local === "tr" || local === "tc") {
    return `${local}:${canonicalSha256(deriveTableLocation(part, node))}`;
  }
  if (local === "sectPr") return "section-properties";
  if (local === "pgSz") {
    return `page-size:${canonicalSha256({
      width: wordAttribute(node, "w") ?? null,
      height: wordAttribute(node, "h") ?? null,
      orientation: wordAttribute(node, "orient") ?? null,
    })}`;
  }
  if (local === "pgMar") {
    return `page-margins:${canonicalSha256({
      top: wordAttribute(node, "top") ?? null,
      right: wordAttribute(node, "right") ?? null,
      bottom: wordAttribute(node, "bottom") ?? null,
      left: wordAttribute(node, "left") ?? null,
      header: wordAttribute(node, "header") ?? null,
      footer: wordAttribute(node, "footer") ?? null,
      gutter: wordAttribute(node, "gutter") ?? null,
    })}`;
  }
  if (local === "gridSpan" || local === "vMerge") {
    return `${local}:${wordAttribute(node, "val") ?? "present"}`;
  }
  if (local === "br") {
    return `break:${wordAttribute(node, "type") ?? "line"}`;
  }
  return null;
}

function staticRunFormattingDescriptor(
  part: IndexedBindingPart,
  textNode: IndexedBindingNode,
): unknown {
  let run: IndexedBindingNode | null = textNode.parent;
  while (run && !isWordElement(run, "r")) run = run.parent;
  const properties = run ? directWordChild(part, run, "rPr") : undefined;
  const property = (localName: string) =>
    properties ? directWordChild(part, properties, localName) : undefined;
  const fonts = property("rFonts");
  const color = property("color");
  const highlight = property("highlight");
  const size = property("sz");
  const complexSize = property("szCs");
  const style = property("rStyle");
  const hidden = (localName: "vanish" | "webHidden" | "specVanish") => {
    const candidate = property(localName);
    return candidate ? parseWordOnOff(candidate) : false;
  };
  return {
    hidden: {
      vanish: hidden("vanish"),
      webHidden: hidden("webHidden"),
      specVanish: hidden("specVanish"),
    },
    fonts: fonts
      ? {
          ascii: wordAttribute(fonts, "ascii") ?? null,
          hAnsi: wordAttribute(fonts, "hAnsi") ?? null,
          eastAsia: wordAttribute(fonts, "eastAsia") ?? null,
          complexScript: wordAttribute(fonts, "cs") ?? null,
          asciiTheme: wordAttribute(fonts, "asciiTheme") ?? null,
          hAnsiTheme: wordAttribute(fonts, "hAnsiTheme") ?? null,
          eastAsiaTheme: wordAttribute(fonts, "eastAsiaTheme") ?? null,
          complexScriptTheme: wordAttribute(fonts, "cstheme") ?? null,
        }
      : null,
    color: color
      ? {
          value: wordAttribute(color, "val") ?? null,
          theme: wordAttribute(color, "themeColor") ?? null,
          tint: wordAttribute(color, "themeTint") ?? null,
          shade: wordAttribute(color, "themeShade") ?? null,
        }
      : null,
    highlight: highlight ? (wordAttribute(highlight, "val") ?? null) : null,
    sizeHalfPoints: size ? (wordAttribute(size, "val") ?? null) : null,
    complexSizeHalfPoints: complexSize
      ? (wordAttribute(complexSize, "val") ?? null)
      : null,
    runStyle: style ? (wordAttribute(style, "val") ?? null) : null,
  };
}

function nodeText(node: OrderedXmlNode): string {
  const value = node[tagOf(node)];
  if (typeof value === "string") return decodeXmlScalar(value);
  if (!Array.isArray(value)) return "";
  return value
    .map((child) =>
      tagOf(child as OrderedXmlNode) === "#text"
        ? decodeXmlScalar(String((child as OrderedXmlNode)["#text"] ?? ""))
        : "",
    )
    .join("");
}

function legacyResultText(
  part: IndexedBindingPart,
  begin: IndexedBindingNode,
): string {
  let paragraph: IndexedBindingNode | null = begin;
  while (paragraph && !isWordElement(paragraph, "p"))
    paragraph = paragraph.parent;
  if (!paragraph) return "";
  const nodes = descendantsLocal(part, paragraph, "");
  const startIndex = nodes.findIndex((candidate) => candidate === begin);
  let depth = 0;
  let inResult = false;
  const text: string[] = [];
  for (const candidate of nodes.slice(startIndex)) {
    if (isWordElement(candidate, "fldChar")) {
      const type = wordAttribute(candidate, "fldCharType");
      if (type === "begin") depth += 1;
      else if (type === "separate" && depth === 1) inResult = true;
      else if (type === "end") {
        depth -= 1;
        if (depth === 0) break;
      }
      continue;
    }
    if (inResult && depth === 1 && isWordElement(candidate, "t")) {
      text.push(nodeText(candidate.node));
    }
  }
  return text.join("");
}

function legacyProofContainer(begin: IndexedBindingNode): IndexedBindingNode {
  let paragraph: IndexedBindingNode | null = begin;
  while (paragraph && !isWordElement(paragraph, "p"))
    paragraph = paragraph.parent;
  return paragraph ?? begin;
}

function legacyCheckboxGlyph(
  part: IndexedBindingPart,
  begin: IndexedBindingNode,
): "☒" | "☐" {
  const paragraph = legacyProofContainer(begin);
  const glyphs = descendantsWord(part, paragraph, "t")
    .flatMap((candidate) => [...nodeText(candidate.node)])
    .filter((value): value is "☒" | "☐" => value === "☒" || value === "☐");
  if (glyphs.length !== 1)
    throw new Error("Legacy checkbox glyph is ambiguous.");
  return glyphs[0]!;
}
