import { createHash } from 'node:crypto';

import JSZip from 'jszip';

import { canonicalSha256 } from '../template-twin/canonical';
import {
  FieldResolutionSchema,
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinValidationResultSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../template-twin/ir';
import { compileTemplateDocx } from './compiler';
import type { TemplateDocxLimits } from './limits';
import { inspectDocxPackage } from './package-security';
import { readbackTemplateDocxOutput } from './output-readback';
import {
  applyApprovedXmlPatches,
  descendantXmlElements,
  descendantWordElements,
  directXmlChild,
  directWordChild,
  encodeXmlPart,
  failTemplateDocxRender,
  scanXmlPart,
  TemplateDocxRenderError,
  verifyRenderedTemplateDocx,
  xmlLocalName,
  type ApprovedXmlPatch,
  type RenderedFieldProof,
  type RenderedPartProof,
  type ScannedXmlPart,
  type TemplateDocxRoundTripVerification,
  type XmlElementSpan,
} from './roundtrip-verify';

const MAX_RENDERED_FIELD_CHARACTERS = 32_767;
const INVALID_XML_CHARACTER_RE =
  /[\u0000-\u0008\u000b\u000c\u000e-\u001f\ud800-\udfff]/u;

type ScalarRenderValue = string | number | boolean | string[] | null;

interface PreparedResolution {
  value: ScalarRenderValue;
  selectedOptionOrdinal: number | null;
}

interface MutablePartPlan {
  scan: ScannedXmlPart;
  patches: ApprovedXmlPatch[];
}

export interface RenderTemplateDocxInput {
  /** Bytes read from the immutable source-artifact key after SHA verification. */
  source: Uint8Array;
  ir: TemplateDocIR;
  resolutions: ReadonlyArray<FieldResolution>;
  /** Result of the independent resolver-output validator. */
  validation: TemplateTwinValidationResult;
  limits?: Partial<TemplateDocxLimits>;
}

export interface RenderTemplateDocxResult {
  readonly document: Buffer;
  readonly outputSha256: string;
  readonly rendererVersion: typeof TEMPLATE_TWIN_RENDERER_VERSION;
  readonly verification: TemplateDocxRoundTripVerification;
}

/**
 * Clones the immutable source package and patches only compiler-approved
 * bindings. This function never logs field values and returns only value hashes
 * in its verification manifest.
 */
export async function renderTemplateDocx(
  input: RenderTemplateDocxInput,
): Promise<RenderTemplateDocxResult> {
  const ir = parseIr(input.ir);
  const validation = parseValidation(input.validation);
  if (
    !validation.valid ||
    validation.issues.some((issue) => issue.severity === 'blocking')
  ) {
    failTemplateDocxRender('VALIDATION_REQUIRED');
  }

  const inspected = inspectDocxPackage(input.source, input.limits);
  assertSourceMatchesIr(input.source, ir, inspected.sourceSha256, input.limits);
  const resolutions = parseResolutions(ir, input.resolutions);
  const partPlans = new Map<string, MutablePartPlan>();

  const getPartPlan = (partName: string): MutablePartPlan => {
    const existing = partPlans.get(partName);
    if (existing) return existing;
    const entry = inspected.zip.entries.get(partName);
    if (!entry) failTemplateDocxRender('BINDING_NOT_FOUND');
    const created = { scan: scanXmlPart(entry.bytes), patches: [] };
    partPlans.set(partName, created);
    return created;
  };

  const repeatingFields = ir.fields.filter((field) => field.rowPrototype);
  const repeatingFieldIds = new Set(
    repeatingFields.map((field) => field.fieldId),
  );
  renderRepeatingRows({
    ir,
    fields: repeatingFields,
    resolutions,
    getPartPlan,
  });

  for (const field of ir.fields) {
    if (repeatingFieldIds.has(field.fieldId)) continue;
    const resolution = resolutions.get(field.fieldId)!;
    if (field.detectionStatus === 'unsupported') {
      if (resolution.value !== null)
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      continue;
    }
    const prepared = prepareScalarResolution(field, resolution);
    const part = getPartPlan(field.rendererBinding.partName);
    const patches = createFieldPatches(part.scan, field, prepared);
    if (patches.length === 0) continue;
    part.patches.push(...patches);
  }

  const partProofs: RenderedPartProof[] = [];
  const patchedPartBytes = new Map<string, Buffer>();
  for (const [partName, plan] of partPlans) {
    if (plan.patches.length === 0) continue;
    const outputText = applyApprovedXmlPatches(plan.scan.text, plan.patches);
    patchedPartBytes.set(
      partName,
      encodeXmlPart(outputText, plan.scan.encoding, plan.scan.hadBom),
    );
    partProofs.push({ partName, patches: plan.patches });
  }

  let output: Buffer = Buffer.from(input.source);
  if (patchedPartBytes.size > 0) {
    try {
      const zip = await JSZip.loadAsync(output, {
        checkCRC32: true,
        createFolders: false,
      });
      for (const [partName, bytes] of patchedPartBytes) {
        const original = zip.file(partName);
        const sourceEntry = inspected.zip.entries.get(partName);
        if (!original || !sourceEntry)
          failTemplateDocxRender('BINDING_NOT_FOUND');
        zip.file(partName, bytes, {
          binary: true,
          createFolders: false,
          date: original.date,
          comment: original.comment,
          unixPermissions: original.unixPermissions,
          dosPermissions: original.dosPermissions,
          compression:
            sourceEntry.compressionMethod === 0 ? 'STORE' : 'DEFLATE',
          compressionOptions:
            sourceEntry.compressionMethod === 0 ? undefined : { level: 6 },
        });
      }
      const platform = Object.values(zip.files).some(
        (entry) =>
          entry.unixPermissions !== null && entry.unixPermissions !== undefined,
      )
        ? 'UNIX'
        : 'DOS';
      output = await zip.generateAsync({
        type: 'nodebuffer',
        compression: 'DEFLATE',
        compressionOptions: { level: 6 },
        platform,
      });
    } catch (cause) {
      if (cause instanceof TemplateDocxRenderError) throw cause;
      throw new TemplateDocxRenderError('PACKAGE_WRITE_FAILED', { cause });
    }
  }

  const plannedFieldProofs = ir.fields.map((field) => {
    const resolution = resolutions.get(field.fieldId)!;
    const occurrences =
      field.rowPrototype && Array.isArray(resolution.value)
        ? resolution.value.length
        : 1;
    return fieldProof(field, resolution.value, occurrences);
  });
  const structuralVerification = verifyRenderedTemplateDocx({
    source: input.source,
    output,
    ir,
    plan: { parts: partProofs, fields: plannedFieldProofs },
    limits: input.limits,
  });
  const outputFields = readbackTemplateDocxOutput({
    source: input.source,
    output,
    ir,
    resolutions: [...resolutions.values()],
    limits: input.limits,
  });
  const verification: TemplateDocxRoundTripVerification = Object.freeze({
    ...structuralVerification,
    fields: outputFields.map((field) => ({
      ...field,
      status: 'verified' as const,
    })),
  });
  const outputSha256 = createHash('sha256').update(output).digest('hex');
  if (verification.outputSha256 !== outputSha256) {
    failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
  }
  return Object.freeze({
    document: output,
    outputSha256,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    verification,
  });
}

function parseIr(ir: TemplateDocIR): TemplateDocIR {
  const parsed = TemplateDocIRSchema.safeParse(ir);
  if (!parsed.success) failTemplateDocxRender('SOURCE_IR_MISMATCH');
  return parsed.data;
}

function parseValidation(
  validation: TemplateTwinValidationResult,
): TemplateTwinValidationResult {
  const parsed = TemplateTwinValidationResultSchema.safeParse(validation);
  if (!parsed.success) failTemplateDocxRender('VALIDATION_REQUIRED');
  return parsed.data;
}

function assertSourceMatchesIr(
  source: Uint8Array,
  ir: TemplateDocIR,
  sourceSha256: string,
  limits?: Partial<TemplateDocxLimits>,
): void {
  if (
    sourceSha256 !== ir.source.sha256 ||
    source.byteLength !== ir.source.sizeBytes
  ) {
    failTemplateDocxRender('SOURCE_IR_MISMATCH');
  }
  const compiled = compileTemplateDocx(source, { limits });
  // The draft 1.1 alpha can render through 1.2 only when every independently
  // recompiled structure, field, table, and static hash below is unchanged.
  // A source that gains the new profile therefore fails closed and must create
  // and certify a new immutable version; unchanged older templates keep working.
  if (
    !(
      compiled.compilerVersion === ir.compilerVersion ||
      (ir.compilerVersion === 'template-docx-compiler/1.1.0' &&
        compiled.compilerVersion === TEMPLATE_TWIN_COMPILER_VERSION)
    ) ||
    compiled.structureSha256 !== ir.structureSha256 ||
    compiled.staticContentSha256 !== ir.staticContentSha256 ||
    canonicalSha256(compiled.parts) !== canonicalSha256(ir.parts) ||
    canonicalSha256(compiled.fields) !== canonicalSha256(ir.fields) ||
    canonicalSha256(compiled.tables) !== canonicalSha256(ir.tables)
  ) {
    failTemplateDocxRender('SOURCE_IR_MISMATCH');
  }
}

function parseResolutions(
  ir: TemplateDocIR,
  rawResolutions: ReadonlyArray<FieldResolution>,
): Map<string, FieldResolution> {
  if (rawResolutions.length !== ir.fields.length) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
  const fieldIds = new Set(ir.fields.map((field) => field.fieldId));
  const fieldById = new Map(ir.fields.map((field) => [field.fieldId, field]));
  const resolutions = new Map<string, FieldResolution>();
  for (const raw of rawResolutions) {
    const parsed = FieldResolutionSchema.safeParse(raw);
    if (
      !parsed.success ||
      !fieldIds.has(parsed.data.fieldId) ||
      resolutions.has(parsed.data.fieldId)
    ) {
      failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
    }
    assertResolutionStatus(fieldById.get(parsed.data.fieldId)!, parsed.data);
    resolutions.set(parsed.data.fieldId, parsed.data);
  }
  if (resolutions.size !== ir.fields.length) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
  return resolutions;
}

function assertResolutionStatus(
  field: TemplateField,
  resolution: FieldResolution,
): void {
  const populatedStatuses = new Set([
    'supported',
    'explicitly_denied',
    'approved_practice_default',
  ]);
  if (resolution.value === null) {
    if (
      populatedStatuses.has(resolution.status) ||
      resolution.selectedOptionOrdinal !== null
    ) {
      failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
    }
    return;
  }
  if (!populatedStatuses.has(resolution.status)) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
  if (
    resolution.status === 'explicitly_denied' &&
    (field.kind !== 'checkbox' || resolution.value !== false)
  ) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
  if (
    field.kind === 'checkbox' &&
    resolution.value === false &&
    resolution.status !== 'explicitly_denied'
  ) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
}

function prepareScalarResolution(
  field: TemplateField,
  resolution: FieldResolution,
): PreparedResolution {
  if (
    field.kind !== 'single_select' &&
    resolution.selectedOptionOrdinal !== null
  ) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  if (Array.isArray(resolution.value)) {
    if (
      field.kind !== 'multi_select' ||
      resolution.value.some((value) => typeof value !== 'string')
    ) {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    return {
      value: resolution.value as string[],
      selectedOptionOrdinal: resolution.selectedOptionOrdinal,
    };
  }
  return {
    value: resolution.value,
    selectedOptionOrdinal: resolution.selectedOptionOrdinal,
  };
}

function renderRepeatingRows(input: {
  ir: TemplateDocIR;
  fields: TemplateField[];
  resolutions: ReadonlyMap<string, FieldResolution>;
  getPartPlan(partName: string): MutablePartPlan;
}): void {
  const byTable = new Map<string, TemplateField[]>();
  for (const field of input.fields) {
    if (!field.tableId || !field.rendererBinding.repeatAncestorPath) {
      failTemplateDocxRender('UNSUPPORTED_BINDING');
    }
    const group = byTable.get(field.tableId) ?? [];
    group.push(field);
    byTable.set(field.tableId, group);
  }

  for (const [tableId, fields] of byTable) {
    const table = input.ir.tables.find(
      (candidate) => candidate.tableId === tableId,
    );
    if (
      !table ||
      table.kind !== 'repeating_table' ||
      table.repeatPrototypeRow === null ||
      fields.some((field) => field.rendererBinding.partName !== table.partName)
    ) {
      failTemplateDocxRender('UNSUPPORTED_BINDING');
    }
    const part = input.getPartPlan(table.partName);
    const tableNode = part.scan.byPath.get(table.path);
    if (!tableNode || xmlLocalName(tableNode.name) !== 'tbl') {
      failTemplateDocxRender('BINDING_NOT_FOUND');
    }
    const rows = tableRows(tableNode);
    const prototypeRow = rows[table.repeatPrototypeRow];
    if (!prototypeRow || rows.length !== table.rowCount) {
      failTemplateDocxRender('BINDING_NOT_FOUND');
    }
    const prototype = repeatingItemContainer(prototypeRow, tableNode);
    if (
      fields.some((field) => {
        const bound = part.scan.byPath.get(field.rendererBinding.path);
        return (
          !bound || bound.start < prototype.start || bound.end > prototype.end
        );
      })
    ) {
      failTemplateDocxRender('BINDING_AMBIGUOUS');
    }

    const lengths = new Set<number>();
    for (const field of fields) {
      const resolution = input.resolutions.get(field.fieldId)!;
      if (resolution.value === null) continue;
      if (!isRowRecordArray(resolution.value)) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      lengths.add(resolution.value.length);
    }
    if (lengths.size > 1) failTemplateDocxRender('FIELD_VALUE_INVALID');
    const rowCount = [...lengths][0] ?? 1;
    if (rowCount < 1 || rowCount > table.maxRows) {
      failTemplateDocxRender('TABLE_ROW_LIMIT_EXCEEDED');
    }

    const renderedRows: string[] = [];
    for (let rowOrdinal = 0; rowOrdinal < rowCount; rowOrdinal += 1) {
      const rowPatches: ApprovedXmlPatch[] = [];
      for (const field of fields) {
        const resolution = input.resolutions.get(field.fieldId)!;
        if (field.detectionStatus === 'unsupported') {
          if (resolution.value !== null)
            failTemplateDocxRender('FIELD_VALUE_INVALID');
          continue;
        }
        const prepared = rowPreparedResolution(field, resolution, rowOrdinal);
        rowPatches.push(...createFieldPatches(part.scan, field, prepared));
      }
      const relativePatches = rowPatches.map((patch) => ({
        ...patch,
        start: patch.start - prototype.start,
        end: patch.end - prototype.start,
      }));
      renderedRows.push(
        applyApprovedXmlPatches(
          part.scan.text.slice(prototype.start, prototype.end),
          relativePatches,
        ),
      );
    }

    const renderedFieldIds = fields
      .filter((field) => field.detectionStatus !== 'unsupported')
      .map((field) => field.fieldId);
    if (renderedFieldIds.length === 0) continue;
    part.patches.push({
      start: prototype.start,
      end: prototype.end,
      replacement: renderedRows.join(''),
      fieldIds: renderedFieldIds,
      kind: 'repeating_row',
    });
  }
}

function tableRows(table: XmlElementSpan): XmlElementSpan[] {
  const rows: XmlElementSpan[] = [];
  const visit = (node: XmlElementSpan): void => {
    for (const child of node.children) {
      const local = xmlLocalName(child.name);
      if (local === 'tbl') continue;
      if (local === 'tr') {
        rows.push(child);
        continue;
      }
      visit(child);
    }
  };
  visit(table);
  return rows;
}

function repeatingItemContainer(
  row: XmlElementSpan,
  table: XmlElementSpan,
): XmlElementSpan {
  let candidate = row.parent;
  while (candidate && candidate !== table) {
    if (xmlLocalName(candidate.name) === 'sdt') {
      const properties = directXmlChild(candidate, 'sdtPr');
      if (
        properties &&
        descendantXmlElements(properties, 'repeatingSectionItem').length > 0
      ) {
        return candidate;
      }
    }
    candidate = candidate.parent;
  }
  return row;
}

function isRowRecordArray(
  value: FieldResolution['value'],
): value is Array<Record<string, string | null>> {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === 'object' && entry !== null && !Array.isArray(entry),
    )
  );
}

function rowPreparedResolution(
  field: TemplateField,
  resolution: FieldResolution,
  rowOrdinal: number,
): PreparedResolution {
  if (resolution.value === null) {
    return { value: null, selectedOptionOrdinal: null };
  }
  if (!isRowRecordArray(resolution.value)) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  if (resolution.selectedOptionOrdinal !== null) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  const row = resolution.value[rowOrdinal];
  if (
    !row ||
    typeof row.value !== 'string' ||
    typeof row.sourceFactId !== 'string' ||
    !resolution.sourceFactIds.includes(row.sourceFactId) ||
    typeof row.evidenceAnchorId !== 'string' ||
    !resolution.evidenceAnchorIds.includes(row.evidenceAnchorId)
  ) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }
  const ordinal =
    row.optionOrdinal === null || row.optionOrdinal === undefined
      ? null
      : parseNonnegativeInteger(row.optionOrdinal);
  let value: ScalarRenderValue = row.value;
  if (field.kind === 'checkbox') {
    if (row.value !== 'true' && row.value !== 'false') {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    value = row.value === 'true';
  } else if (field.kind === 'number') {
    const parsed = Number(row.value);
    if (!Number.isFinite(parsed) || String(parsed) !== row.value) {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    value = parsed;
  } else if (field.kind === 'multi_select') {
    value = row.value.split(';').map((entry) => entry.trim());
  }
  return { value, selectedOptionOrdinal: ordinal };
}

function parseNonnegativeInteger(value: string): number {
  if (!/^(?:0|[1-9][0-9]*)$/.test(value)) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  return Number(value);
}

function createFieldPatches(
  part: ScannedXmlPart,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const binding = field.rendererBinding;
  const bound = part.byPath.get(binding.path);
  if (!bound) failTemplateDocxRender('BINDING_NOT_FOUND');
  switch (binding.bindingType) {
    case 'content_control':
      if (xmlLocalName(bound.name) !== 'sdt') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      return contentControlPatches(part.text, bound, field, resolution);
    case 'legacy_form_field':
      if (xmlLocalName(bound.name) !== 'fldChar') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      return legacyFieldPatches(part.text, bound, field, resolution);
    case 'table_cell':
      if (xmlLocalName(bound.name) !== 'tc') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      return tableCellPatches(part.text, bound, field, resolution);
    case 'repeating_row':
      failTemplateDocxRender('UNSUPPORTED_BINDING');
  }
}

function contentControlPatches(
  xml: string,
  control: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const properties = directWordChild(control, 'sdtPr');
  const content = directWordChild(control, 'sdtContent');
  if (!properties || !content) failTemplateDocxRender('BINDING_NOT_FOUND');
  const placeholderPatches =
    resolution.value === null
      ? []
      : placeholderMetadataPatches(xml, properties, content, field.fieldId);

  if (field.kind === 'checkbox') {
    const checkbox = descendantXmlElements(properties, 'checkbox')[0];
    const checked = checkbox
      ? descendantXmlElements(checkbox, 'checked')[0]
      : undefined;
    if (!checkbox || !checked) failTemplateDocxRender('BINDING_NOT_FOUND');
    if (resolution.value !== null && typeof resolution.value !== 'boolean') {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    // A missing/unknown checkbox is a third state, not a denial. Preserve the
    // physician's source control byte-for-byte until affirmative or explicitly
    // denied evidence resolves it. This contract applies before both the state
    // attribute and visible glyph are patched.
    if (resolution.value === null) return [];
    const selected = resolution.value === true;
    const state = selected
      ? descendantXmlElements(checkbox, 'checkedState')[0]
      : descendantXmlElements(checkbox, 'uncheckedState')[0];
    const glyph = state
      ? glyphFromWordCode(readXmlAttribute(xml, state, 'val'))
      : selected
        ? '☒'
        : '☐';
    return [
      ...placeholderPatches,
      setXmlAttributePatch(
        xml,
        checked,
        'val',
        selected ? '1' : '0',
        field.fieldId,
      ),
      ...textContainerPatches(xml, content, glyph, field.fieldId),
    ];
  }

  if (field.kind === 'date') {
    const date = directWordChild(properties, 'date');
    if (!date) failTemplateDocxRender('BINDING_NOT_FOUND');
    const display = formatDateValue(xml, date, resolution.value);
    const statePatch =
      resolution.value === null
        ? removeXmlAttributePatch(xml, date, 'fullDate', field.fieldId)
        : setXmlAttributePatch(
            xml,
            date,
            'fullDate',
            `${String(resolution.value)}T00:00:00Z`,
            field.fieldId,
          );
    return [
      ...placeholderPatches,
      ...(statePatch ? [statePatch] : []),
      ...textContainerPatches(xml, content, display, field.fieldId),
    ];
  }

  if (field.kind === 'single_select') {
    const comboBox = directWordChild(properties, 'comboBox');
    const lastValue = comboBox
      ? descendantXmlElements(comboBox, 'lastValue')[0]
      : undefined;
    if (resolution.value === null) {
      return [
        ...(lastValue ? [removeXmlElementPatch(lastValue, field.fieldId)] : []),
        ...textContainerPatches(xml, content, '', field.fieldId),
      ];
    }
    const option = exactSelectedOption(field, resolution);
    return [
      ...placeholderPatches,
      ...(lastValue
        ? [
            setXmlAttributePatch(
              xml,
              lastValue,
              'val',
              option.value,
              field.fieldId,
            ),
          ]
        : []),
      ...textContainerPatches(
        xml,
        content,
        safeDisplayText(option.displayText),
        field.fieldId,
      ),
    ];
  }

  const display = displayValue(field, resolution);
  return [
    ...placeholderPatches,
    ...textContainerPatches(xml, content, display, field.fieldId),
  ];
}

function placeholderMetadataPatches(
  xml: string,
  properties: XmlElementSpan,
  content: XmlElementSpan,
  fieldId: string,
): ApprovedXmlPatch[] {
  const patches = descendantWordElements(properties, 'showingPlcHdr').map(
    (node) => removeXmlElementPatch(node, fieldId),
  );
  for (const style of descendantWordElements(content, 'rStyle')) {
    if (readXmlAttribute(xml, style, 'val') === 'PlaceholderText') {
      patches.push(removeXmlElementPatch(style, fieldId));
    }
  }
  return patches;
}

function legacyFieldPatches(
  xml: string,
  begin: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const formData = descendantWordElements(begin, 'ffData')[0];
  if (!formData) failTemplateDocxRender('BINDING_NOT_FOUND');
  // Legacy FORMCHECKBOX fields use the same tri-state clinical contract as
  // native content controls. An unresolved value must not be coerced to 0 or
  // have its visible result text cleared.
  if (field.kind === 'checkbox' && resolution.value === null) return [];
  const patches: ApprovedXmlPatch[] = [];
  const display = displayValue(field, resolution);

  if (field.kind === 'single_select') {
    const list = descendantWordElements(formData, 'ddList')[0];
    if (!list) failTemplateDocxRender('BINDING_NOT_FOUND');
    const result = descendantWordElements(list, 'result')[0];
    if (resolution.value === null) {
      if (result) patches.push(removeXmlElementPatch(result, field.fieldId));
    } else {
      const ordinal = exactSelectedOption(field, resolution).ordinal;
      patches.push(
        result
          ? setXmlAttributePatch(
              xml,
              result,
              'val',
              String(ordinal),
              field.fieldId,
            )
          : insertXmlChildPatch(
              xml,
              list,
              list.children.find(
                (child) => xmlLocalName(child.name) === 'listEntry',
              ),
              wordElement(list, 'result', ordinal),
              field.fieldId,
            ),
      );
    }
  } else if (field.kind === 'checkbox') {
    const checkbox = descendantWordElements(formData, 'checkBox')[0];
    if (!checkbox) failTemplateDocxRender('BINDING_NOT_FOUND');
    const checked = descendantWordElements(checkbox, 'checked')[0];
    if (resolution.value !== null && typeof resolution.value !== 'boolean') {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    const value = resolution.value === true ? '1' : '0';
    patches.push(
      checked
        ? setXmlAttributePatch(xml, checked, 'val', value, field.fieldId)
        : appendXmlChildPatch(
            xml,
            checkbox,
            wordElement(checkbox, 'checked', value),
            field.fieldId,
          ),
    );
  } else {
    const textInput = descendantWordElements(formData, 'textInput')[0];
    if (!textInput) failTemplateDocxRender('BINDING_NOT_FOUND');
    const currentDefault = descendantWordElements(textInput, 'default')[0];
    if (resolution.value === null) {
      if (currentDefault) {
        patches.push(removeXmlElementPatch(currentDefault, field.fieldId));
      }
    } else {
      patches.push(
        currentDefault
          ? setXmlAttributePatch(
              xml,
              currentDefault,
              'val',
              display,
              field.fieldId,
            )
          : insertXmlChildPatch(
              xml,
              textInput,
              textInput.children.find((child) =>
                ['maxLength', 'format'].includes(xmlLocalName(child.name)),
              ),
              wordElement(textInput, 'default', display),
              field.fieldId,
            ),
      );
    }
  }

  const resultTextNodes = legacyResultTextNodes(xml, begin);
  if (resultTextNodes.length > 0) {
    patches.push(
      ...patchExistingTextNodes(xml, resultTextNodes, display, field.fieldId),
    );
  }
  return patches;
}

function tableCellPatches(
  xml: string,
  cell: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  if (field.rendererBinding.bindingProfile === 'TAB_ONLY_BLANK_TABLE_CELL_V1') {
    return tabOnlyBlankTableCellPatches(xml, cell, field, resolution);
  }
  if (field.kind === 'checkbox' && resolution.value === null) return [];
  const display = displayValue(field, resolution);
  const textNodes = descendantWordElements(cell, 't');
  if (textNodes.length > 0) {
    return patchExistingTextNodes(xml, textNodes, display, field.fieldId);
  }
  if (display === '') return [];
  const paragraph = descendantXmlElements(cell, 'p')[0];
  if (!paragraph) failTemplateDocxRender('BINDING_NOT_FOUND');
  const prefix = qualifiedPrefix(paragraph.name);
  const run = `<${prefix}r><${prefix}t>${escapeXmlText(display)}</${prefix}t></${prefix}r>`;
  return [appendXmlChildPatch(xml, paragraph, run, field.fieldId)];
}

function tabOnlyBlankTableCellPatches(
  xml: string,
  cell: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const cellChildren = cell.children;
  const paragraphs = cellChildren.filter(
    (child) =>
      child.namespaceUri === cell.namespaceUri &&
      xmlLocalName(child.name) === 'p',
  );
  if (
    paragraphs.length !== 1 ||
    cellChildren.filter(
      (child) =>
        child.namespaceUri === cell.namespaceUri &&
        xmlLocalName(child.name) === 'tcPr',
    ).length > 1 ||
    cellChildren.some(
      (child) =>
        child.namespaceUri !== cell.namespaceUri ||
        !['tcPr', 'p'].includes(xmlLocalName(child.name)),
    )
  ) {
    failTemplateDocxRender('BINDING_AMBIGUOUS');
  }
  const paragraph = paragraphs[0]!;
  const paragraphProperties = directWordChild(paragraph, 'pPr');
  if (
    !paragraphProperties ||
    paragraph.children.length !== 1 ||
    paragraph.children[0] !== paragraphProperties
  ) {
    failTemplateDocxRender('BINDING_AMBIGUOUS');
  }
  const tabSets = paragraphProperties.children.filter(
    (child) =>
      child.namespaceUri === paragraphProperties.namespaceUri &&
      xmlLocalName(child.name) === 'tabs',
  );
  if (
    tabSets.length !== 1 ||
    tabSets[0]!.children.length === 0 ||
    tabSets[0]!.children.some(
      (child) =>
        child.namespaceUri !== paragraphProperties.namespaceUri ||
        xmlLocalName(child.name) !== 'tab',
    )
  ) {
    failTemplateDocxRender('BINDING_AMBIGUOUS');
  }
  if (resolution.value === null) return [];
  const display = safeDisplayText(displayValue(field, resolution));
  if (
    display.includes('\t') ||
    display.includes('\r') ||
    display.includes('\n')
  ) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  const prefix = qualifiedPrefix(paragraph.name);
  const preserve = /^\s|\s$/u.test(display) ? ' xml:space="preserve"' : '';
  const run =
    `<${prefix}r><${prefix}t${preserve}>` +
    `${escapeXmlText(display)}</${prefix}t></${prefix}r>`;
  return [appendXmlChildPatch(xml, paragraph, run, field.fieldId)];
}

function displayValue(
  field: TemplateField,
  resolution: PreparedResolution,
): string {
  if (resolution.value === null) return '';
  switch (field.kind) {
    case 'narrative_text':
      if (typeof resolution.value !== 'string') {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return safeDisplayText(resolution.value);
    case 'single_select':
      return safeDisplayText(
        exactSelectedOption(field, resolution).displayText,
      );
    case 'multi_select': {
      if (!Array.isArray(resolution.value)) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      const values = resolution.value.map((value) => {
        const option = field.allowedOptions.find(
          (candidate) => candidate.value === value,
        );
        if (!option) failTemplateDocxRender('FIELD_VALUE_INVALID');
        return option.displayText;
      });
      if (new Set(resolution.value).size !== resolution.value.length) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return safeDisplayText(values.join('; '));
    }
    case 'checkbox':
      if (typeof resolution.value !== 'boolean') {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return resolution.value ? '☒' : '☐';
    case 'date':
      if (
        typeof resolution.value !== 'string' ||
        !isStrictIsoDate(resolution.value)
      ) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return resolution.value;
    case 'number':
      if (
        typeof resolution.value !== 'number' ||
        !Number.isFinite(resolution.value)
      ) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return String(resolution.value);
    case 'measurement':
      if (
        (typeof resolution.value !== 'number' ||
          !Number.isFinite(resolution.value)) &&
        typeof resolution.value !== 'string'
      ) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      return safeDisplayText(String(resolution.value));
  }
}

function exactSelectedOption(
  field: TemplateField,
  resolution: PreparedResolution,
): TemplateField['allowedOptions'][number] {
  if (
    typeof resolution.value !== 'string' ||
    resolution.selectedOptionOrdinal === null
  ) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  const option = field.allowedOptions.find(
    (candidate) => candidate.ordinal === resolution.selectedOptionOrdinal,
  );
  if (!option || option.value !== resolution.value) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  return option;
}

function formatDateValue(
  xml: string,
  dateControl: XmlElementSpan,
  value: ScalarRenderValue,
): string {
  if (value === null) return '';
  if (typeof value !== 'string' || !isStrictIsoDate(value)) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  const formatNode = descendantXmlElements(dateControl, 'dateFormat')[0];
  const format = formatNode ? readXmlAttribute(xml, formatNode, 'val') : null;
  if (!format) return value;
  const [year, month, day] = value.split('-');
  if (
    !year ||
    !month ||
    !day ||
    /[A-Za-z]/.test(format.replace(/yyyy|yy|MM|M|dd|d/g, ''))
  ) {
    return value;
  }
  return format.replace(/yyyy|yy|MM|M|dd|d/g, (token) => {
    switch (token) {
      case 'yyyy':
        return year;
      case 'yy':
        return year.slice(-2);
      case 'MM':
        return month;
      case 'M':
        return String(Number(month));
      case 'dd':
        return day;
      case 'd':
        return String(Number(day));
      default:
        return token;
    }
  });
}

function isStrictIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
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

function safeDisplayText(value: string): string {
  if (
    value.length > MAX_RENDERED_FIELD_CHARACTERS ||
    INVALID_XML_CHARACTER_RE.test(value)
  ) {
    failTemplateDocxRender(
      value.length > MAX_RENDERED_FIELD_CHARACTERS
        ? 'FIELD_VALUE_TOO_LARGE'
        : 'FIELD_VALUE_INVALID',
    );
  }
  return value;
}

function textContainerPatches(
  xml: string,
  container: XmlElementSpan,
  display: string,
  fieldId: string,
): ApprovedXmlPatch[] {
  const textNodes = descendantWordElements(container, 't');
  if (textNodes.length === 0) failTemplateDocxRender('BINDING_NOT_FOUND');
  return patchExistingTextNodes(
    xml,
    textNodes,
    safeDisplayText(display),
    fieldId,
  );
}

function patchExistingTextNodes(
  xml: string,
  nodes: XmlElementSpan[],
  display: string,
  fieldId: string,
): ApprovedXmlPatch[] {
  return nodes.map((node, index) =>
    textNodePatch(xml, node, index === 0 ? display : '', fieldId),
  );
}

function textNodePatch(
  xml: string,
  node: XmlElementSpan,
  value: string,
  fieldId: string,
): ApprovedXmlPatch {
  if (xmlLocalName(node.name) !== 't')
    failTemplateDocxRender('BINDING_NOT_FOUND');
  const escaped = escapeXmlText(value);
  const hasWordWhitespaceControls = /[\r\n\t]/.test(value);
  const needsPreserve = /^\s|\s(?:\r\n|\r|\n|\t)|\s$/.test(value);
  if (!node.selfClosing && !hasWordWhitespaceControls && !needsPreserve) {
    return {
      start: node.startTagEnd,
      end: node.endTagStart,
      replacement: escaped,
      fieldIds: [fieldId],
      kind: 'field_content',
    };
  }

  const rawStartTag = xml.slice(node.start, node.startTagEnd);
  const openTag = ensureOpenTextTag(rawStartTag, needsPreserve);
  const prefix = qualifiedPrefix(node.name);
  const tokens = value.split(/(\r\n|\r|\n|\t)/);
  const body = tokens
    .map((token, index) => {
      if (token === '\t') return `<${prefix}tab/>`;
      if (token === '\r' || token === '\n' || token === '\r\n') {
        return `<${prefix}br/>`;
      }
      if (!token && index > 0) return '';
      const tokenOpenTag =
        index === 0
          ? openTag
          : `<${node.name}${/^\s|\s$/.test(token) ? ' xml:space="preserve"' : ''}>`;
      return `${tokenOpenTag}${escapeXmlText(token)}</${node.name}>`;
    })
    .join('');
  return {
    start: node.start,
    end: node.end,
    replacement: body || `${openTag}</${node.name}>`,
    fieldIds: [fieldId],
    kind: 'field_content',
  };
}

function ensureOpenTextTag(rawStartTag: string, preserve: boolean): string {
  let open = rawStartTag.replace(/\/\s*>$/, '>');
  if (preserve && !/\sxml:space\s*=/.test(open)) {
    open = open.replace(/>$/, ' xml:space="preserve">');
  }
  return open;
}

function escapeXmlText(value: string): string {
  return safeDisplayText(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function escapeXmlAttribute(value: string): string {
  return escapeXmlText(value)
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

interface AttributeLocation {
  name: string;
  fullStart: number;
  fullEnd: number;
  valueStart: number;
  valueEnd: number;
}

function findXmlAttribute(
  xml: string,
  node: XmlElementSpan,
  localName: string,
): AttributeLocation | null {
  const tag = xml.slice(node.start, node.startTagEnd);
  const expression = /\s+([^\s=/>]+)\s*=\s*(["'])([\s\S]*?)\2/g;
  for (const match of tag.matchAll(expression)) {
    const name = match[1]!;
    if (xmlLocalName(name) !== localName || match.index === undefined) continue;
    const quoteOffset = match[0].indexOf(match[2]!);
    const valueStart = node.start + match.index + quoteOffset + 1;
    return {
      name,
      fullStart: node.start + match.index,
      fullEnd: node.start + match.index + match[0].length,
      valueStart,
      valueEnd: valueStart + match[3]!.length,
    };
  }
  return null;
}

function readXmlAttribute(
  xml: string,
  node: XmlElementSpan,
  localName: string,
): string | null {
  const location = findXmlAttribute(xml, node, localName);
  return location ? xml.slice(location.valueStart, location.valueEnd) : null;
}

function setXmlAttributePatch(
  xml: string,
  node: XmlElementSpan,
  localName: string,
  value: string,
  fieldId: string,
): ApprovedXmlPatch {
  const location = findXmlAttribute(xml, node, localName);
  if (location) {
    return {
      start: location.valueStart,
      end: location.valueEnd,
      replacement: escapeXmlAttribute(value),
      fieldIds: [fieldId],
      kind: 'control_state',
    };
  }
  const startTag = xml.slice(node.start, node.startTagEnd);
  const closeOffset = startTag.search(/\/?\s*>$/);
  if (closeOffset < 0) failTemplateDocxRender('BINDING_NOT_FOUND');
  const qualifiedName = `${qualifiedPrefix(node.name)}${localName}`;
  return {
    start: node.start + closeOffset,
    end: node.start + closeOffset,
    replacement: ` ${qualifiedName}="${escapeXmlAttribute(value)}"`,
    fieldIds: [fieldId],
    kind: 'control_state',
  };
}

function removeXmlAttributePatch(
  xml: string,
  node: XmlElementSpan,
  localName: string,
  fieldId: string,
): ApprovedXmlPatch | null {
  const location = findXmlAttribute(xml, node, localName);
  if (!location) return null;
  return {
    start: location.fullStart,
    end: location.fullEnd,
    replacement: '',
    fieldIds: [fieldId],
    kind: 'control_state',
  };
}

function appendXmlChildPatch(
  xml: string,
  parent: XmlElementSpan,
  childXml: string,
  fieldId: string,
): ApprovedXmlPatch {
  if (!parent.selfClosing) {
    return {
      start: parent.endTagStart,
      end: parent.endTagStart,
      replacement: childXml,
      fieldIds: [fieldId],
      kind: 'field_content',
    };
  }
  const raw = xml.slice(parent.start, parent.end);
  const open = raw.replace(/\/\s*>$/, '>');
  return {
    start: parent.start,
    end: parent.end,
    replacement: `${open}${childXml}</${parent.name}>`,
    fieldIds: [fieldId],
    kind: 'field_content',
  };
}

function insertXmlChildPatch(
  xml: string,
  parent: XmlElementSpan,
  before: XmlElementSpan | undefined,
  childXml: string,
  fieldId: string,
): ApprovedXmlPatch {
  if (!before) return appendXmlChildPatch(xml, parent, childXml, fieldId);
  if (before.parent !== parent || parent.selfClosing) {
    failTemplateDocxRender('BINDING_AMBIGUOUS');
  }
  return {
    start: before.start,
    end: before.start,
    replacement: childXml,
    fieldIds: [fieldId],
    kind: 'field_content',
  };
}

function removeXmlElementPatch(
  node: XmlElementSpan,
  fieldId: string,
): ApprovedXmlPatch {
  return {
    start: node.start,
    end: node.end,
    replacement: '',
    fieldIds: [fieldId],
    kind: 'control_state',
  };
}

function wordElement(
  parent: XmlElementSpan,
  localName: string,
  value: string | number,
): string {
  const prefix = qualifiedPrefix(parent.name);
  return `<${prefix}${localName} ${prefix}val="${escapeXmlAttribute(String(value))}"/>`;
}

function qualifiedPrefix(name: string): string {
  const colon = name.indexOf(':');
  return colon < 0 ? '' : `${name.slice(0, colon)}:`;
}

function glyphFromWordCode(value: string | null): string {
  if (!value || !/^[a-f0-9]{1,6}$/i.test(value)) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  const codePoint = Number.parseInt(value, 16);
  if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) {
    failTemplateDocxRender('FIELD_VALUE_INVALID');
  }
  return String.fromCodePoint(codePoint);
}

function legacyResultTextNodes(
  xml: string,
  begin: XmlElementSpan,
): XmlElementSpan[] {
  let paragraph: XmlElementSpan | null = begin.parent;
  while (paragraph && xmlLocalName(paragraph.name) !== 'p') {
    paragraph = paragraph.parent;
  }
  if (!paragraph) return [];
  const fieldCharacters = descendantWordElements(paragraph, 'fldChar');
  const beginIndex = fieldCharacters.findIndex(
    (candidate) => candidate === begin,
  );
  if (beginIndex < 0) failTemplateDocxRender('BINDING_AMBIGUOUS');
  let depth = 0;
  let separate: XmlElementSpan | null = null;
  let end: XmlElementSpan | null = null;
  for (const character of fieldCharacters.slice(beginIndex)) {
    const type = readXmlAttribute(xml, character, 'fldCharType');
    if (type === 'begin') {
      depth += 1;
      continue;
    }
    if (type === 'separate' && depth === 1) {
      if (separate) failTemplateDocxRender('BINDING_AMBIGUOUS');
      separate = character;
      continue;
    }
    if (type === 'end') {
      depth -= 1;
      if (depth === 0) {
        end = character;
        break;
      }
      if (depth < 0) failTemplateDocxRender('BINDING_AMBIGUOUS');
    }
  }
  if (!separate || !end) return [];
  return descendantWordElements(paragraph, 't').filter(
    (node) => node.start >= separate!.end && node.end <= end!.start,
  );
}

function fieldProof(
  field: TemplateField,
  value: FieldResolution['value'],
  occurrences: number,
): RenderedFieldProof {
  return {
    fieldId: field.fieldId,
    partName: field.rendererBinding.partName,
    bindingPath: field.rendererBinding.path,
    valueSha256: canonicalSha256({ fieldId: field.fieldId, value }),
    occurrences,
    disposition:
      field.detectionStatus === 'unsupported'
        ? 'preserved_unsupported'
        : value === null
          ? field.kind === 'checkbox'
            ? 'preserved_unresolved'
            : 'unresolved_blank'
          : 'rendered',
  };
}
