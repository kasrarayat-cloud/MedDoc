import { canonicalSha256 } from '../template-twin/canonical';
import type {
  FieldResolution,
  TemplateDocIR,
  TemplateField,
} from '../template-twin/ir';
import type { TemplateDocxLimits } from './limits';
import { inspectDocxPackage } from './package-security';
import {
  TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
  certifiedBindingFingerprintSha256,
  deriveOoxmlBindingIdentity,
  deriveTableLocation,
  hasStrongNativeIdentity,
  indexBindingXmlPart,
  nativeIdentityFromRendererBinding,
  rendererBindingFingerprintSha256,
  sameNativeIdentity,
  type BindingTableLocation,
  type DerivedOoxmlBindingIdentity,
  type IndexedBindingNode as IndexedNode,
  type IndexedBindingPart as IndexedPart,
} from './binding-fingerprint';
import {
  WORDPROCESSINGML_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  childrenOf,
  exactExpandedAttribute,
  parseOrderedXml,
  tagOf,
  type OrderedXmlNode,
} from './xml';
import {
  failTemplateDocxRender,
  type RenderedFieldProof,
} from './roundtrip-verify';

export interface ReadbackTemplateDocxOutputInput {
  readonly source: Uint8Array;
  readonly output: Uint8Array;
  readonly ir: TemplateDocIR;
  readonly resolutions: readonly FieldResolution[];
  readonly limits?: Partial<TemplateDocxLimits>;
}

interface FieldBindingRecord {
  readonly field: TemplateField;
  readonly partName: string;
  readonly part: IndexedPart;
  readonly node: IndexedNode;
  readonly identity: DerivedOoxmlBindingIdentity;
  readonly tableLocation: BindingTableLocation;
  readonly repeatAncestorCanonicalPath: string | null;
  readonly occurrences: number;
  ordinal: number;
}

/**
 * Independently reparses completed DOCX bytes. It does not receive renderer
 * patch objects and derives every value hash from the output package itself.
 */
export function readbackTemplateDocxOutput(
  input: ReadbackTemplateDocxOutputInput,
): RenderedFieldProof[] {
  const sourcePackage = inspectDocxPackage(input.source, input.limits);
  const outputPackage = inspectDocxPackage(input.output, input.limits);
  const resolutions = new Map(
    input.resolutions.map((resolution) => [resolution.fieldId, resolution]),
  );
  if (
    resolutions.size !== input.ir.fields.length ||
    input.resolutions.length !== input.ir.fields.length
  ) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }

  const sourceParts = new Map<string, IndexedPart>();
  const outputParts = new Map<string, IndexedPart>();
  const loadPart = (
    partName: string,
    source: boolean,
  ): IndexedPart => {
    const cache = source ? sourceParts : outputParts;
    const existing = cache.get(partName);
    if (existing) return existing;
    const entry = (source ? sourcePackage : outputPackage).zip.entries.get(
      partName,
    );
    if (!entry) failTemplateDocxRender('BINDING_NOT_FOUND');
    let indexed: IndexedPart;
    try {
      indexed = indexBindingXmlPart(
        parseOrderedXml(
          entry.bytes,
          (source ? sourcePackage : outputPackage).limits,
        ),
      );
    } catch {
      failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    }
    cache.set(partName, indexed);
    return indexed;
  };

  const structuralPartNames = [
    sourcePackage.mainPartName,
    ...sourcePackage.headerPartNames,
    ...sourcePackage.footerPartNames,
  ];
  if (
    canonicalSha256(structuralPartNames) !==
    canonicalSha256([
      outputPackage.mainPartName,
      ...outputPackage.headerPartNames,
      ...outputPackage.footerPartNames,
    ])
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  for (const partName of structuralPartNames) {
    loadPart(partName, true);
    loadPart(partName, false);
  }
  const sourceIdentityPartNames = [...sourcePackage.zip.entries.keys()]
    .filter((partName) => /^word\/.*\.xml$/i.test(partName))
    .sort();
  const outputIdentityPartNames = [...outputPackage.zip.entries.keys()]
    .filter((partName) => /^word\/.*\.xml$/i.test(partName))
    .sort();
  if (
    canonicalSha256(sourceIdentityPartNames) !==
    canonicalSha256(outputIdentityPartNames)
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  for (const partName of sourceIdentityPartNames) {
    loadPart(partName, true);
    loadPart(partName, false);
  }
  assertPackageBindingCensus(
    sourceParts,
    outputParts,
    sourceIdentityPartNames,
  );

  const sourceRecords = input.ir.fields.map((field) =>
    certifiedSourceRecord(field, loadPart(field.rendererBinding.partName, true)),
  );
  assignOutputDerivedOrdinals(sourceRecords, structuralPartNames);
  for (const record of sourceRecords) assertCertifiedSourceRecord(record);

  const outputRecords = sourceRecords.map((sourceRecord) =>
    locateOutputBinding(sourceRecord, outputParts, structuralPartNames),
  );
  assignOutputDerivedOrdinals(outputRecords, structuralPartNames);

  return outputRecords.map((outputRecord) => {
    const field = outputRecord.field;
    const resolution = resolutions.get(field.fieldId);
    if (!resolution) failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
    const sourceRecord = sourceRecords.find(
      (candidate) => candidate.field.fieldId === field.fieldId,
    );
    if (!sourceRecord) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    const bindingEvidence = verifiedBindingEvidence(sourceRecord, outputRecord);
    const occurrences = outputRecord.occurrences;

    if (field.rowPrototype) {
      // Repeating structures are certification-blocked in safe alpha. A
      // future extractor/renderer must introduce independent row identities.
      if (resolution.value !== null) failTemplateDocxRender('UNSUPPORTED_BINDING');
    }

    if (resolution.value === null || field.detectionStatus === 'unsupported') {
      if (resolution.value !== null) failTemplateDocxRender('FIELD_VALUE_INVALID');
      const mustBePreserved =
        field.detectionStatus === 'unsupported' ||
        field.kind === 'checkbox' ||
        field.rowPrototype;
      if (mustBePreserved) {
        if (
          canonicalSha256(proofContainer(sourceRecord.node)) !==
          canonicalSha256(proofContainer(outputRecord.node))
        ) {
          failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
        }
      } else if (!isBlankBinding(outputRecord.part, outputRecord.node, field)) {
        failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      }
      return {
        fieldId: field.fieldId,
        partName: field.rendererBinding.partName,
        bindingPath: field.rendererBinding.path,
        bindingEvidence,
        valueSha256: fieldValueSha256(field.fieldId, null),
        occurrences,
        disposition:
          field.detectionStatus === 'unsupported'
            ? 'preserved_unsupported'
            : mustBePreserved
              ? 'preserved_unresolved'
              : 'unresolved_blank',
      };
    }

    const actual = readFieldValue(outputRecord.part, outputRecord.node, field);
    if (fieldValueSha256(field.fieldId, actual) !== fieldValueSha256(field.fieldId, resolution.value)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return {
      fieldId: field.fieldId,
      partName: field.rendererBinding.partName,
      bindingPath: field.rendererBinding.path,
      bindingEvidence,
      valueSha256: fieldValueSha256(field.fieldId, actual),
      occurrences,
      disposition: 'rendered',
    };
  });
}

function assertPackageBindingCensus(
  sourceParts: ReadonlyMap<string, IndexedPart>,
  outputParts: ReadonlyMap<string, IndexedPart>,
  identityPartNames: readonly string[],
): void {
  const census = (parts: ReadonlyMap<string, IndexedPart>) =>
    identityPartNames.flatMap((partName) => {
      const part = parts.get(partName);
      if (!part) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
      return part.nodes.flatMap((node) => {
        if (isWordElement(node, 'sdt')) {
          const identity = deriveOoxmlBindingIdentity(
            part,
            node,
            'content_control',
          );
          return [
            identity
              ? {
                  partName,
                  canonicalPath: node.canonicalPath,
                  bindingType: 'content_control',
                  nativeIdentity: identity.nativeIdentity,
                  identitySha256: identity.identitySha256,
                }
              : {
                  partName,
                  canonicalPath: node.canonicalPath,
                  bindingType: 'malformed_content_control',
                  nodeSha256: canonicalSha256(node.node),
                },
          ];
        }
        if (isWordElement(node, 'fldChar')) {
          const identity = deriveOoxmlBindingIdentity(
            part,
            node,
            'legacy_form_field',
          );
          return [
            identity
              ? {
                  partName,
                  canonicalPath: node.canonicalPath,
                  bindingType: 'legacy_form_field',
                  nativeIdentity: identity.nativeIdentity,
                  identitySha256: identity.identitySha256,
                }
              : {
                  partName,
                  canonicalPath: node.canonicalPath,
                  bindingType: 'word_field_marker',
                  fieldMarkerType: wordAttribute(node, 'fldCharType') ?? null,
                  nodeSha256: canonicalSha256(node.node),
                },
          ];
        }
        return [];
      });
    });
  if (canonicalSha256(census(sourceParts)) !== canonicalSha256(census(outputParts))) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
}

function deriveRepeatAncestorCanonicalPath(
  part: IndexedPart,
  node: IndexedNode,
  expectedCanonicalPath: string | null,
): string | null {
  if (!expectedCanonicalPath) return null;
  const expectedSourceAncestor = part.byCanonicalPath.get(expectedCanonicalPath);
  if (expectedSourceAncestor && isAncestor(expectedSourceAncestor, node)) {
    return expectedSourceAncestor.canonicalPath;
  }
  const terminalSegment = expectedCanonicalPath.slice(
    expectedCanonicalPath.lastIndexOf('/') + 1,
  );
  let ancestor = node.parent;
  while (ancestor) {
    if (ancestor.canonicalPath.endsWith(`/${terminalSegment}`)) {
      return ancestor.canonicalPath;
    }
    ancestor = ancestor.parent;
  }
  return null;
}

function isAncestor(ancestor: IndexedNode, node: IndexedNode): boolean {
  let current = node.parent;
  while (current) {
    if (current === ancestor) return true;
    current = current.parent;
  }
  return false;
}

function certifiedSourceRecord(
  field: TemplateField,
  part: IndexedPart,
): FieldBindingRecord {
  const node = part.byPath.get(field.rendererBinding.path);
  if (!node) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  const identity = deriveOoxmlBindingIdentity(
    part,
    node,
    field.rendererBinding.bindingType,
  );
  if (!identity) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  return {
    field,
    partName: field.rendererBinding.partName,
    part,
    node,
    identity,
    tableLocation: deriveTableLocation(part, node),
    repeatAncestorCanonicalPath: deriveRepeatAncestorCanonicalPath(
      part,
      node,
      field.rendererBinding.canonicalRepeatAncestorPath,
    ),
    occurrences: 1,
    ordinal: -1,
  };
}

function assertCertifiedSourceRecord(record: FieldBindingRecord): void {
  const binding = record.field.rendererBinding;
  const { certifiedBindingSha256, ...unsignedBinding } = binding;
  if (
    record.node.canonicalPath !== binding.canonicalPath ||
    record.node.path !== binding.path ||
    canonicalSha256(record.node.node) !== binding.sourceControlSha256 ||
    record.identity.bindingType !== binding.bindingType ||
    record.identity.identitySha256 !== binding.sourceBindingIdentitySha256 ||
    !sameNativeIdentity(
      record.identity.nativeIdentity,
      nativeIdentityFromRendererBinding(binding),
    ) ||
    canonicalSha256(record.tableLocation) !==
      canonicalSha256({
        tableIndex: binding.tableIndex,
        rowIndex: binding.rowIndex,
        cellIndex: binding.cellIndex,
      }) ||
    record.repeatAncestorCanonicalPath !==
      binding.canonicalRepeatAncestorPath ||
    record.ordinal !== binding.ordinal ||
    rendererBindingFingerprintSha256(record.field.fieldId, unsignedBinding) !==
      certifiedBindingSha256
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
}

function locateOutputBinding(
  source: FieldBindingRecord,
  outputParts: ReadonlyMap<string, IndexedPart>,
  structuralPartNames: readonly string[],
): FieldBindingRecord {
  const binding = source.field.rendererBinding;
  const matches: Array<{
    partName: string;
    part: IndexedPart;
    node: IndexedNode;
    identity: DerivedOoxmlBindingIdentity;
  }> = [];
  for (const partName of structuralPartNames) {
    const part = outputParts.get(partName);
    if (!part) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    const candidates =
      binding.bindingType === 'table_cell'
        ? partName === binding.partName
          ? part.nodes.filter((node) => {
              const location = deriveTableLocation(part, node);
              return (
                isWordElement(node, 'tc') &&
                location.tableIndex === binding.tableIndex &&
                location.rowIndex === binding.rowIndex &&
                location.cellIndex === binding.cellIndex
              );
            })
          : []
        : part.nodes;
    for (const node of candidates) {
      const identity = deriveOoxmlBindingIdentity(part, node, binding.bindingType);
      if (!identity) continue;
      const identityMatches = hasStrongNativeIdentity(source.identity.nativeIdentity)
        ? sameNativeIdentity(identity.nativeIdentity, source.identity.nativeIdentity)
        : identity.identitySha256 === source.identity.identitySha256;
      if (
        identityMatches &&
        identity.identitySha256 === source.identity.identitySha256
      ) {
        matches.push({ partName, part, node, identity });
      }
    }
  }
  if (matches.length !== 1) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  const match = matches[0]!;
  return {
    field: source.field,
    partName: match.partName,
    part: match.part,
    node: match.node,
    identity: match.identity,
    tableLocation: deriveTableLocation(match.part, match.node),
    repeatAncestorCanonicalPath: deriveRepeatAncestorCanonicalPath(
      match.part,
      match.node,
      binding.canonicalRepeatAncestorPath,
    ),
    occurrences: matches.length,
    ordinal: -1,
  };
}

function assignOutputDerivedOrdinals(
  records: FieldBindingRecord[],
  structuralPartNames: readonly string[],
): void {
  const partOrder = new Map(
    structuralPartNames.map((partName, index) => [partName, index]),
  );
  const ordered = [...records].sort((left, right) => {
    const partDifference =
      (partOrder.get(left.partName) ?? Number.MAX_SAFE_INTEGER) -
      (partOrder.get(right.partName) ?? Number.MAX_SAFE_INTEGER);
    return partDifference || left.node.order - right.node.order;
  });
  ordered.forEach((record, ordinal) => {
    record.ordinal = ordinal;
  });
}

function verifiedBindingEvidence(
  source: FieldBindingRecord,
  output: FieldBindingRecord,
): RenderedFieldProof['bindingEvidence'] {
  const binding = source.field.rendererBinding;
  const outputFingerprintSha256 = certifiedBindingFingerprintSha256({
    fieldId: source.field.fieldId,
    partName: output.partName,
    canonicalPath: output.node.canonicalPath,
    bindingType: output.identity.bindingType,
    bindingOrdinal: output.ordinal,
    nativeIdentity: output.identity.nativeIdentity,
    sourceControlSha256: binding.sourceControlSha256,
    sourceBindingIdentitySha256: output.identity.identitySha256,
    tableLocation: output.tableLocation,
    canonicalRepeatAncestorPath: output.repeatAncestorCanonicalPath,
  });
  if (outputFingerprintSha256 !== binding.certifiedBindingSha256) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  return {
    contractVersion: TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
    status: 'verified',
    certifiedFingerprintSha256: binding.certifiedBindingSha256,
    outputFingerprintSha256,
    outputPartName: output.partName,
    outputCanonicalPath: output.node.canonicalPath,
    outputBindingType: output.identity.bindingType,
    outputBindingOrdinal: output.ordinal,
    outputNativeIdentity: output.identity.nativeIdentity,
    outputBindingIdentitySha256: output.identity.identitySha256,
    outputTableLocation: output.tableLocation,
  };
}

function isBlankBinding(
  part: IndexedPart,
  bound: IndexedNode,
  field: TemplateField,
): boolean {
  if (field.rendererBinding.bindingType === 'content_control') {
    const properties = directWordChild(bound, 'sdtPr', part);
    const content = directWordChild(bound, 'sdtContent', part);
    if (!properties || !content || wordText(content, part) !== '') return false;
    if (field.kind === 'date') {
      return !wordAttribute(directWordChild(properties, 'date', part), 'fullDate');
    }
    if (field.kind === 'single_select') {
      const combo = directWordChild(properties, 'comboBox', part);
      return !combo || !wordAttribute(descendantsWord(combo, 'lastValue', part)[0], 'val');
    }
    return true;
  }
  if (field.rendererBinding.bindingType === 'legacy_form_field') {
    const formData = descendantsWord(bound, 'ffData', part)[0];
    if (!formData || legacyResultText(bound, part) !== '') return false;
    if (field.kind === 'single_select') {
      const list = descendantsWord(formData, 'ddList', part)[0];
      return !wordAttribute(
        list ? descendantsWord(list, 'result', part)[0] : undefined,
        'val',
      );
    }
    const textInput = descendantsWord(formData, 'textInput', part)[0];
    return !wordAttribute(
      textInput ? descendantsWord(textInput, 'default', part)[0] : undefined,
      'val',
    );
  }
  if (field.rendererBinding.bindingType === 'table_cell') {
    return wordText(bound, part) === '';
  }
  return false;
}

function proofContainer(node: IndexedNode): OrderedXmlNode {
  if (node.visit.localName !== 'fldChar') return node.node;
  let parent: IndexedNode | null = node;
  while (parent && !isWordElement(parent, 'p')) parent = parent.parent;
  return parent?.node ?? node.node;
}

function readFieldValue(
  part: IndexedPart,
  bound: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  switch (field.rendererBinding.bindingType) {
    case 'content_control':
      return readContentControl(part, bound, field);
    case 'legacy_form_field':
      return readLegacyField(part, bound, field);
    case 'table_cell':
      return convertDisplayedValue(field, wordText(bound, part));
    case 'repeating_row':
      failTemplateDocxRender('UNSUPPORTED_BINDING');
  }
}

function readContentControl(
  part: IndexedPart,
  control: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  if (!isWordElement(control, 'sdt')) failTemplateDocxRender('BINDING_NOT_FOUND');
  const properties = directWordChild(control, 'sdtPr', part);
  const content = directWordChild(control, 'sdtContent', part);
  if (!properties || !content) failTemplateDocxRender('BINDING_NOT_FOUND');
  if (
    descendantsWord(properties, 'showingPlcHdr', part).length > 0 ||
    descendantsWord(content, 'rStyle', part).some(
      (style) => wordAttribute(style, 'val') === 'PlaceholderText',
    )
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }

  if (field.kind === 'checkbox') {
    const checkbox = descendantsByLocal(properties, 'checkbox', part).find(
      (node) => node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
    );
    const checked = checkbox
      ? descendantsByLocal(checkbox, 'checked', part).find(
          (node) => node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
        )
      : undefined;
    const raw = namespacedAttribute(
      checked,
      WORDPROCESSINGML_2010_NAMESPACE,
      'val',
    );
    if (raw !== '0' && raw !== '1' && raw !== 'true' && raw !== 'false') {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const value = raw === '1' || raw === 'true';
    const state = checkbox
      ? descendantsByLocal(
          checkbox,
          value ? 'checkedState' : 'uncheckedState',
          part,
        ).find(
          (node) =>
            node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
        )
      : undefined;
    const glyphCode = namespacedAttribute(
      state,
      WORDPROCESSINGML_2010_NAMESPACE,
      'val',
    );
    const glyph = glyphCode && /^[a-f0-9]{1,6}$/i.test(glyphCode)
      ? String.fromCodePoint(Number.parseInt(glyphCode, 16))
      : value
        ? '☒'
        : '☐';
    if (wordText(content, part) !== glyph) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }

  if (field.kind === 'date') {
    const date = directWordChild(properties, 'date', part);
    const fullDate = wordAttribute(date, 'fullDate');
    const match = /^(\d{4}-\d{2}-\d{2})T/.exec(fullDate ?? '');
    if (!date || !match) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    const value = match[1]!;
    const format = wordAttribute(descendantsWord(date, 'dateFormat', part)[0], 'val');
    if (wordText(content, part) !== formatDate(value, format)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }

  const value = convertDisplayedValue(field, wordText(content, part));
  if (field.kind === 'single_select') {
    const combo = directWordChild(properties, 'comboBox', part);
    const lastValue = combo
      ? wordAttribute(descendantsWord(combo, 'lastValue', part)[0], 'val')
      : undefined;
    if (lastValue !== undefined && lastValue !== value) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
  }
  return value;
}

function readLegacyField(
  part: IndexedPart,
  begin: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  const formData = descendantsWord(begin, 'ffData', part)[0];
  if (!formData) failTemplateDocxRender('BINDING_NOT_FOUND');
  const resultText = legacyResultText(begin, part);
  if (field.kind === 'checkbox') {
    const checkbox = descendantsWord(formData, 'checkBox', part)[0];
    const raw = wordAttribute(
      checkbox ? descendantsWord(checkbox, 'checked', part)[0] : undefined,
      'val',
    );
    if (raw !== '0' && raw !== '1' && raw !== 'true' && raw !== 'false') {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const value = raw === '1' || raw === 'true';
    if (resultText && resultText !== (value ? '☒' : '☐')) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }
  if (field.kind === 'single_select') {
    const list = descendantsWord(formData, 'ddList', part)[0];
    const raw = wordAttribute(
      list ? descendantsWord(list, 'result', part)[0] : undefined,
      'val',
    );
    if (!raw || !/^(?:0|[1-9][0-9]*)$/.test(raw)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const option = field.allowedOptions.find((candidate) => candidate.ordinal === Number(raw));
    if (!option || (resultText && resultText !== option.displayText)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return option.value;
  }
  const textInput = descendantsWord(formData, 'textInput', part)[0];
  const defaultValue = wordAttribute(
    textInput ? descendantsWord(textInput, 'default', part)[0] : undefined,
    'val',
  );
  if (defaultValue !== undefined && defaultValue !== null && resultText && defaultValue !== resultText) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  return convertDisplayedValue(field, defaultValue ?? resultText);
}

function convertDisplayedValue(
  field: TemplateField,
  displayed: string,
): FieldResolution['value'] {
  if (field.kind === 'single_select') {
    const options = field.allowedOptions.filter(
      (option) => option.displayText === displayed,
    );
    if (options.length !== 1) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    return options[0]!.value;
  }
  if (field.kind === 'multi_select') {
    const displayedOptions = displayed.split(';').map((value) => value.trim());
    const values = displayedOptions.map((display) => {
      const options = field.allowedOptions.filter(
        (option) => option.displayText === display,
      );
      if (options.length !== 1) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      return options[0]!.value;
    });
    if (new Set(values).size !== values.length) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return values;
  }
  if (field.kind === 'number') {
    const number = Number(displayed);
    if (!Number.isFinite(number) || String(number) !== displayed) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return number;
  }
  return displayed;
}

function legacyResultText(begin: IndexedNode, part: IndexedPart): string {
  let paragraph: IndexedNode | null = begin;
  while (paragraph && !isWordElement(paragraph, 'p')) paragraph = paragraph.parent;
  if (!paragraph) return '';
  const nodes = descendantsByLocal(paragraph, '', part);
  const startIndex = nodes.findIndex((node) => node === begin);
  let depth = 0;
  let inResult = false;
  const text: string[] = [];
  for (const node of nodes.slice(startIndex)) {
    if (isWordElement(node, 'fldChar')) {
      const type = wordAttribute(node, 'fldCharType');
      if (type === 'begin') depth += 1;
      else if (type === 'separate' && depth === 1) inResult = true;
      else if (type === 'end') {
        depth -= 1;
        if (depth === 0) break;
      }
      continue;
    }
    if (inResult && depth === 1 && isWordElement(node, 't')) {
      text.push(nodeText(node.node));
    }
  }
  return text.join('');
}

function directWordChild(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode | undefined {
  return childrenOf(node.node)
    .map((child) => part.byNode.get(child))
    .find((child): child is IndexedNode => Boolean(child && isWordElement(child, wanted)));
}

function descendantsWord(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode[] {
  return descendantsByLocal(node, wanted, part).filter(
    (candidate) => candidate.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE,
  );
}

function descendantsByLocal(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode[] {
  const output: IndexedNode[] = [];
  const stack = [...childrenOf(node.node)].reverse();
  while (stack.length > 0) {
    const child = stack.pop()!;
    if (tagOf(child) === '#text' || tagOf(child) === '?xml') continue;
    const indexed = part.byNode.get(child);
    if (!indexed) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    if (!wanted || indexed.visit.localName === wanted) output.push(indexed);
    const grandchildren = childrenOf(child);
    for (let index = grandchildren.length - 1; index >= 0; index -= 1) {
      stack.push(grandchildren[index]!);
    }
  }
  return output;
}

function isWordElement(node: IndexedNode, wanted: string): boolean {
  return (
    node.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    node.visit.localName === wanted
  );
}

function wordAttribute(
  node: IndexedNode | undefined,
  local: string,
): string | undefined {
  if (!node) return undefined;
  return exactExpandedAttribute(node.visit, WORDPROCESSINGML_NAMESPACE, local);
}

function namespacedAttribute(
  node: IndexedNode | undefined,
  namespaceUri: string,
  local: string,
): string | undefined {
  if (!node) return undefined;
  return exactExpandedAttribute(node.visit, namespaceUri, local);
}

function wordText(node: IndexedNode, part: IndexedPart): string {
  const output: string[] = [];
  const nodes = [node, ...descendantsByLocal(node, '', part)];
  for (const candidate of nodes) {
    if (candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
    if (candidate.visit.localName === 't') output.push(nodeText(candidate.node));
    else if (candidate.visit.localName === 'tab') output.push('\t');
    else if (candidate.visit.localName === 'br' || candidate.visit.localName === 'cr') {
      output.push('\n');
    }
  }
  return output.join('');
}

function nodeText(node: OrderedXmlNode): string {
  const value = node[tagOf(node)];
  if (!Array.isArray(value)) return typeof value === 'string' ? value : '';
  return value
    .map((child) =>
      tagOf(child as OrderedXmlNode) === '#text'
        ? String((child as OrderedXmlNode)['#text'] ?? '')
        : '',
    )
    .join('')
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) =>
      String.fromCodePoint(Number.parseInt(hex, 16)),
    )
    .replace(/&#([0-9]+);/g, (_, value: string) =>
      String.fromCodePoint(Number.parseInt(value, 10)),
    )
    .replaceAll('&quot;', '"')
    .replaceAll('&apos;', "'")
    .replaceAll('&gt;', '>')
    .replaceAll('&lt;', '<')
    .replaceAll('&amp;', '&');
}

function formatDate(value: string, format: string | undefined): string {
  if (!format) return value;
  const [year, month, day] = value.split('-');
  if (!year || !month || !day || /[A-Za-z]/.test(format.replace(/yyyy|yy|MM|M|dd|d/g, ''))) {
    return value;
  }
  return format.replace(/yyyy|yy|MM|M|dd|d/g, (token) => {
    if (token === 'yyyy') return year;
    if (token === 'yy') return year.slice(-2);
    if (token === 'MM') return month;
    if (token === 'M') return String(Number(month));
    if (token === 'dd') return day;
    return String(Number(day));
  });
}

function fieldValueSha256(
  fieldId: string,
  value: FieldResolution['value'],
): string {
  return canonicalSha256({ fieldId, value });
}
