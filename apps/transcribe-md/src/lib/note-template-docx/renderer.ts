import { createHash } from 'node:crypto';

import JSZip from 'jszip';

import { canonicalSha256 } from '../template-twin/canonical';
import {
  FieldResolutionSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinValidationResultSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../template-twin/ir';
import { isPrintableDenial } from '../template-twin/denial-contract';
import { compileTemplateDocx } from './compiler';
import type { TemplateDocxLimits } from './limits';
import { inspectDocxPackage } from './package-security';
import {
  applyApprovedXmlPatches,
  descendantXmlElements,
  directXmlChild,
  encodeXmlPart,
  failTemplateDocxRender,
  scanXmlPart,
  TemplateDocxRenderError,
  verifyRenderedTemplateDocx,
  type RenderVerificationPlan,
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
  /**
   * The plan the verifier was given — the patches applied and the proof for
   * each field.
   *
   * ⚠️ RETURNED SO THE ROUND-TRIP GUARANTEE CAN BE CHECKED INDEPENDENTLY.
   * `verifyRenderedTemplateDocx` cannot be driven without a plan, so rule 2's
   * emptied byte comparison had no arm at all and an adversarial lens read it
   * as decoration. It is not persisted: `synthetic-test.ts` stores
   * `verification` alone, and `fill-engine.ts` reads only the document.
   */
  readonly plan: RenderVerificationPlan;
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
  // Read once: a paragraph's numbering can live entirely in `styles.xml`.
  const numberedStyles = numberedStyleIds(inspected);
  assertSourceMatchesIr(input.source, ir, inspected.sourceSha256, input.limits);
  const resolutions = parseResolutions(ir, input.resolutions);
  const partPlans = new Map<string, MutablePartPlan>();
  const fieldProofs: RenderedFieldProof[] = [];

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
  const repeatingFieldIds = new Set(repeatingFields.map((field) => field.fieldId));
  renderRepeatingRows({
    ir,
    fields: repeatingFields,
    resolutions,
    getPartPlan,
    fieldProofs,
    numberedStyles,
  });

  for (const field of ir.fields) {
    if (repeatingFieldIds.has(field.fieldId)) continue;
    const resolution = resolutions.get(field.fieldId)!;
    if (field.detectionStatus === 'unsupported') {
      if (resolution.value !== null) failTemplateDocxRender('FIELD_VALUE_INVALID');
      continue;
    }
    const prepared = prepareScalarResolution(field, resolution);
    const part = getPartPlan(field.rendererBinding.partName);
    const { patches, boundedClear, blankEligible } = createFieldPatches(
      part.scan,
      field,
      prepared,
      numberedStyles,
    );
    if (patches.length === 0) {
      // BLANK PROOF. No patch means the field keeps the template's own unfilled
      // state — a dropdown placeholder, an empty cell. That is a real outcome
      // and the certificate must attest it, so an entry is emitted rather than
      // the field being skipped.
      //
      // Skipping was why certification could not close: the gate requires one
      // proof entry per expected field, and every honestly-blank field silently
      // had none. The verifier checks this entry by comparing the rendered
      // bytes at this binding against the SOURCE's bytes — the blank is proven
      // against the doctor's own canvas, not asserted.
      //
      // occurrences = 1: one binding site, verified. The gate's
      // `expected.occurrences > 0` is satisfied without touching the gate.
      // ⚠️ A ZERO-PATCH FIELD IS ONLY `blank` IF IT MAY CLAIM BLANKNESS.
      // A numbered paragraph whose run is already gone needs no patch, and
      // emitting `blank` unconditionally handed it the credit the numbering
      // rule exists to deny — the same document the patched case correctly
      // refuses, minus an empty run shell.
      // ⚠️ IT STAYS `blank` — THE LABEL IS ABOUT THE WRITE, NOT THE CREDIT.
      // Emitting `filled` here to deny credit broke the verifier outright:
      // `filled` joins the PATCHED set, the patched set must equal the proof
      // set exactly, and this field has no patches. `blank` is the honest
      // label for an unpatched field; the ineligibility rides alongside it.
      fieldProofs.push({
        ...fieldProof(field, resolution.value, 1, 'blank'),
        ...(blankEligible ? {} : { blankEligible: false }),
      });
      continue;
    }
    part.patches.push(...patches);
    // ⚠️ #165 — THE LABEL IS A FACT ABOUT THE WRITE, NOT A CLAIM ABOUT THE KIND.
    //
    // `boundedClear` is true only where `sdtBoundedClearPatches` replaced the
    // control's whole `w:sdtContent` subtree. There is no kind list to keep
    // correct and nothing to enumerate: a checkbox is excluded because we
    // deliberately WRITE its glyph, a selection is included because we
    // demonstrably clear it, and a binding with no bounded container is
    // excluded because no such write happened.
    //
    // An `emptied` proof carries `expectedSpanSha256` — the binding span as this
    // writer meant to leave it. The verifier's single comparison is what makes
    // the claim checkable; a proof without an expectation is refused there.
    fieldProofs.push(
      boundedClear
        ? emptiedProof(
            field,
            resolution.value,
            1,
            expectedEmptiedSpanSha256(part.scan, field, patches),
          )
        : fieldProof(field, resolution.value, 1),
    );
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
        if (!original || !sourceEntry) failTemplateDocxRender('BINDING_NOT_FOUND');
        zip.file(partName, bytes, {
          binary: true,
          createFolders: false,
          date: original.date,
          comment: original.comment,
          unixPermissions: original.unixPermissions,
          dosPermissions: original.dosPermissions,
          compression: sourceEntry.compressionMethod === 0 ? 'STORE' : 'DEFLATE',
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

  const renderPlan = { parts: partProofs, fields: fieldProofs };
  const verification = verifyRenderedTemplateDocx({
    source: input.source,
    output,
    ir,
    plan: renderPlan,
    limits: input.limits,
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
    // ⚠️ THE PLAN IS RETURNED SO THE ROUND-TRIP GUARANTEE IS INDEPENDENTLY
    // CHECKABLE. Without it `verifyRenderedTemplateDocx` cannot be driven from
    // a test at all — it needs a plan — so its emptied byte comparison had no
    // arm and looked like decoration. Only `verification` is persisted
    // (`synthetic-test.ts`), and the single production consumer
    // (`fill-engine.ts`) reads `document`/`outputSha256`, so nothing serialises
    // this object whole.
    plan: renderPlan,
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
  if (
    compiled.compilerVersion !== ir.compilerVersion ||
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
  // ⚠️ OWNER RULING #157(d) — THE WALL ADMITS EXACTLY ONE SHAPE AGAIN.
  //
  // #157(b) widened it to admit `narrative_text` + a string, on the reasoning
  // that the string was the doctor's own dictated sentence. That reasoning was
  // falsified three times (see `denial-contract.ts`'s header), and #157(d)
  // deletes narrative denial printing altogether — so the arm is back to
  // `checkbox` + `false`, the one control whose blank state IS the denial.
  // Everything else is refused: a narrative_text, a single_select, a
  // multi_select, a repeating section, a date, a number, a measurement, and a
  // checkbox holding anything but `false`.
  //
  // ⚠️ THIS ARM REFUSES THE PACKAGE, AND THAT DOES NOT CONTRADICT RULE (3).
  // Rule (3) says no DENIAL may refuse an export, and no legal resolver path
  // can now reach here: a denial that cannot be printed is `denial_withheld`
  // with a null value long before the renderer sees it. Reaching this line
  // means a resolution no producer can mint — a BUG — and laundering a bug
  // into a quiet blank is how a dropdown ends up ticked for a finding the
  // encounter denied.
  if (
    resolution.status === 'explicitly_denied' &&
    !isPrintableDenial(field, resolution.value)
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
  fieldProofs: RenderedFieldProof[];
  numberedStyles: NumberingStyles;
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
    const table = input.ir.tables.find((candidate) => candidate.tableId === tableId);
    if (
      !table ||
      table.kind !== 'repeating_table' ||
      table.repeatPrototypeRow === null ||
      fields.some(
        (field) => field.rendererBinding.partName !== table.partName,
      )
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
        return !bound || bound.start < prototype.start || bound.end > prototype.end;
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
          if (resolution.value !== null) failTemplateDocxRender('FIELD_VALUE_INVALID');
          continue;
        }
        const prepared = rowPreparedResolution(field, resolution, rowOrdinal);
        rowPatches.push(...createFieldPatches(part.scan, field, prepared, input.numberedStyles).patches);
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
    for (const field of fields) {
      if (field.detectionStatus === 'unsupported') continue;
      const resolution = input.resolutions.get(field.fieldId)!;
      // ⚠️ #165 RULE 3 — THIS EMITTER CLASSIFIES DELIBERATELY, AND THE ANSWER
      // IS `filled`. Until #164 this was `filled` only by DEFAULT — the 4th
      // argument was simply never passed — so an identical field got the
      // opposite label purely for sitting in a repeating table. Stating it is
      // the fix; the value is unchanged.
      //
      // It cannot be `emptied`, and the reason is structural rather than a
      // policy choice: these fields are merged into ONE `repeating_row` patch
      // that replaces the prototype with `rowCount` CLONED rows, so there is no
      // 1:1 output span at this field's `bindingPath` to compare against. The
      // byte-equality proof is per-binding-path and simply does not exist here.
      // Fails closed — it under-counts, never over-counts.
      input.fieldProofs.push(fieldProof(field, resolution.value, rowCount, 'filled'));
    }
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
  numberedStyles: NumberingStyles,
): FieldPatchResult {
  const binding = field.rendererBinding;
  const bound = part.byPath.get(binding.path);
  if (!bound) failTemplateDocxRender('BINDING_NOT_FOUND');
  switch (binding.bindingType) {
    case 'content_control':
      if (xmlLocalName(bound.name) !== 'sdt') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      return contentControlPatches(part.text, bound, field, resolution, numberedStyles);
    case 'legacy_form_field':
      if (xmlLocalName(bound.name) !== 'fldChar') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      // ⚠️ LEGACY IS NEVER BOUNDED-CLEARED. Its result has no enclosing
      // element — it is a SPAN between `separate` and `end` fldChars, which is
      // exactly why every attempt to bound it by walking was falsified. It gets
      // no `emptied` proof until its own slice gives it a real container.
      return {
        patches: legacyFieldPatches(part.text, bound, field, resolution),
        boundedClear: false,
        blankEligible: true,
      };
    case 'table_cell':
      if (xmlLocalName(bound.name) !== 'tc') {
        failTemplateDocxRender('BINDING_NOT_FOUND');
      }
      // ⚠️ `table_cell` HAS a bounded container (`w:tc`) and could take the
      // same treatment — ruling #165 rule 2 names it as the next candidate.
      // Until that write exists and is proved, it earns no `emptied` proof.
      return {
        patches: tableCellPatches(part.text, bound, field, resolution),
        boundedClear: false,
        blankEligible: true,
      };
    case 'repeating_row':
      failTemplateDocxRender('UNSUPPORTED_BINDING');
  }
}

/**
 * #165 RULE 1 — A NULL CLEARS A CONTENT CONTROL BY REPLACING ITS WHOLE
 * `w:sdtContent` SUBTREE. THE BOUNDARY IS THE DOCUMENT'S OWN ELEMENT.
 *
 * ⚠️ THIS IS THE DISTINCTION FROM THE FOUR-TIMES-FALSIFIED INSTRUMENT, and it
 * is the entire point of the ruling. Every previous attempt bounded the edit
 * with a scan WE performed — "find the `w:t` descendants", "walk separate→end",
 * "check the region against a list of visible elements". Each was falsified by
 * the next carrier nobody enumerated: `w:sym`, `w:pict`, `w:drawing`,
 * `w:object`, `w:delText`, `w:instrText`. The list never closes.
 *
 * Here nothing is enumerated and nothing is searched. `startTagEnd..endTagStart`
 * are the inner bounds of the control's OWN element, produced by the XML
 * scanner. A glyph, an image, a field code or a tracked deletion inside the
 * control cannot survive, because NOTHING inside the control survives.
 *
 * ⚠️ IT RETURNS `null` — FAIL-CLOSED — WHERE THE CONTAINER IS NOT SAFELY
 * REPLACEABLE, and the caller then falls back to text-node patching and does
 * NOT earn an `emptied` proof:
 *   - a self-closing `w:sdtContent` is already empty; there is nothing to clear
 *     and no write to prove;
 *   - a row- or cell-level control (`w:tr` / `w:tc` children) would have its
 *     table structure destroyed by an inline run, so it is left alone.
 *
 * `w:showingPlcHdr` is removed with the content: it is Word's "what you see is
 * the PLACEHOLDER" flag, and leaving it set on a control we just emptied invites
 * Word to re-display the template's own prompt text. It lives in `sdtPr`, which
 * is inside the approved binding span, so removing it is bounded too.
 */
/**
 * Nodes KEPT WHOLE — structural properties. Never recursed into, never deleted.
 * `w:sectPr` is here because it lives inside `w:pPr`, so keeping `pPr` whole
 * keeps the section wherever the author put it — including the LAST paragraph,
 * which is where it conventionally sits and where v2 lost it.
 */
const STRUCTURE_KEEP_WHOLE: ReadonlySet<string> = new Set([
  'pPr', 'tblPr', 'tblGrid', 'trPr', 'tcPr', 'sectPr', 'sdtPr', 'sdtEndPr',
  'bookmarkStart', 'bookmarkEnd', 'proofErr',
  'commentRangeStart', 'commentRangeEnd',
  // ⚠️ ADDED AFTER THE PASS MEASURED THEIR LOSS. `w:tblPrEx` carries per-row
  // border and shading exceptions, so deleting it silently dropped row borders
  // inside any cleared control; `w:permStart`/`w:permEnd` mark editable ranges.
  // All three are properties, none renders content, and losing them is the
  // inverse failure v1 and v2 died of.
  'tblPrEx', 'permStart', 'permEnd',
  // ⚠️ #168 — A RUN'S OWN PROPERTIES ARE SKELETON. v3 deleted the whole run, so
  // an emptied inline control lost `w:rPr` on all 28 controls of the real
  // template (307 -> 279). An EMPTY run with properties prints nothing, and it
  // is what a doctor TYPING into the cleared control inherits — the capability
  // v3 was silently costing.
  'rPr',
]);

/** Structural containers — kept, and recursed into so their content clears. */
const STRUCTURE_RECURSE: ReadonlySet<string> = new Set([
  'p', 'tbl', 'tr', 'tc', 'sdt', 'sdtContent',
  // ⚠️ BLOCK-LEVEL WRAPPERS ARE RECURSED, NOT DELETED WHOLE — measured.
  // `mc:AlternateContent` is emitted by Word routinely, and deleting it took a
  // table cell's ONLY paragraph with it, leaving `<w:tc><w:tcPr/></w:tc>`:
  // `CT_Tc` requires at least one block-level child, so that is the classic
  // "Word found unreadable content" shape. `w:customXml` did the same to a
  // whole row.
  //
  // ⚠️ AND TRACKED-CHANGE WRAPPERS TOO, for the same reason at a different
  // level: `w:ins`/`w:del`/`w:moveTo`/`w:moveFrom` hold RUNS inline and
  // PARAGRAPHS at block level. Recursing gets both right — the runs go as
  // content, the paragraphs stay as structure — where deleting whole removed a
  // tracked-inserted paragraph entirely.
  'AlternateContent', 'Choice', 'Fallback', 'customXml',
  'ins', 'del', 'moveTo', 'moveFrom',
  // ⚠️ #168 — THE RUN SHELL IS KEPT AND RECURSED, not deleted. Its `w:rPr` is
  // kept whole above; every OTHER child — `w:t`, `w:sym`, `w:tab`, `w:br`,
  // `w:pict`, `w:drawing`, `w:fldChar`, `w:instrText`, and anything nobody has
  // named — is not skeleton and goes. Still a keep-list, still writes nothing,
  // still rewrites no tag.
  'r',
]);

/**
 * #167 RULE 1 v3 — STRUCTURE-KEEP. Delete every node that is not skeleton.
 *
 * ⚠️ NOTHING IS WRITTEN AND NO START TAG IS REWRITTEN. That single property is
 * what retires most of two passes' findings by construction rather than by
 * patch: namespaces declared on a `w:p` survive because that `w:p` is never
 * re-emitted; tables survive because `w:tbl` is skeleton; `w:sectPr` survives
 * wherever it sits because it rides inside `w:pPr`; every paragraph survives
 * because paragraphs are skeleton. v2 lost all four by rebuilding the container
 * from a template of its own.
 *
 * ⚠️ AND IT IS A KEEP-LIST, NOT "DELETE THE RUNS" — the intuition is runs, the
 * mechanism must be the keep-list. OMML is the named counterexample: `m:oMath`
 * and `m:oMathPara` print mathematics and are NOT `w:r`, so a delete-the-runs
 * rule leaves an equation standing in a field proofed blank. Under a keep-list
 * they are simply not skeleton, and go — as does anything nobody has thought
 * of, which is the entire point (canon 86).
 *
 * `w:fldSimple` goes too: an EMPTY simple field is not inert, because the PDF
 * engine may recompute it from its `w:instr` and print a value nobody wrote.
 *
 * ⚠️ CHARACTER DATA IS A REFUSAL, NOT A DELETION. Raw text directly inside a
 * container is not an element, so a walk cannot see it and an emptiness check
 * counting ELEMENTS reads it as "already empty" — measured, a control holding
 * bare `WARFARIN 5 MG DAILY` earned a `blank` proof while printing. It is
 * schema-invalid, so rather than invent a rule for it we refuse the control.
 */
/**
 * Containers OOXML requires to keep at least one child of a given kind. Emptying
 * one of these produces a document Word refuses to open, so the clear REFUSES
 * rather than emit it.
 */
const REQUIRED_CONTENT: ReadonlyMap<string, ReadonlySet<string>> = new Map([
  // CT_Tc requires EG_BlockLevelElts minOccurs=1.
  ['tc', new Set(['p', 'tbl', 'sdt', 'AlternateContent', 'customXml'])],
  // CT_Tbl requires at least one row.
  ['tbl', new Set(['tr', 'sdt', 'AlternateContent', 'customXml'])],
]);

/**
 * Text between elements that a reader would not see: XML comments, CDATA and
 * processing instructions. `scanXmlPart` skips them without registering a child,
 * so their raw bytes land in the gap between siblings — and a naive
 * non-whitespace test then refuses the whole control over a comment Word never
 * displays, silently disarming the clear.
 */
function gapIsInvisible(gap: string): boolean {
  return gap
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<!\[CDATA\[[\s\S]*?\]\]>/g, '')
    .replace(/<\?[\s\S]*?\?>/g, '')
    .trim().length === 0;
}

function structureKeepDeletions(
  xml: string,
  node: XmlElementSpan,
  fieldId: string,
  out: ApprovedXmlPatch[],
): boolean {
  const nodeLocal = xmlLocalName(node.name);
  const required = REQUIRED_CONTENT.get(nodeLocal);
  let survivingRequired = 0;
  let cursor = node.startTagEnd;
  for (const child of node.children) {
    if (!gapIsInvisible(xml.slice(cursor, child.start))) return false;
    cursor = child.end;
    const local = xmlLocalName(child.name);
    if (required?.has(local)) survivingRequired += 1;
    if (STRUCTURE_KEEP_WHOLE.has(local)) {
      // ⚠️ A PROPERTY CONTAINER MUST NOT HOLD A RUN, AND THIS IS THE ONE CHECK
      // THAT KEEPS THE KEEP-LIST HONEST.
      //
      // Canon 86's correction records that the keep-list is a claim about the
      // FORMAT while the code copies subtrees VERBATIM and nothing validates
      // them. A lens then confirmed the gap is live: a `w:r` smuggled inside
      // `w:pPr` survives a clear, prints, and the field is still proofed
      // `emptied` with blank credit — #164's shape, one layer inside the fix.
      //
      // `w:r` is the universal carrier of printable content in OOXML, and no
      // property container legitimately contains one (`w:pPr/w:rPr` is run
      // PROPERTIES, not a run). So this is a single structural rule rather than
      // another enumeration of carriers — and it REFUSES rather than repairs,
      // because a property block holding a run is a document we do not
      // understand.
      if (descendantXmlElements(child, 'r').length > 0) return false;
      continue;
    }
    if (STRUCTURE_RECURSE.has(local)) {
      if (!structureKeepDeletions(xml, child, fieldId, out)) return false;
      continue;
    }
    out.push({
      start: child.start,
      end: child.end,
      replacement: '',
      fieldIds: [fieldId],
      kind: 'field_content',
    });
  }
  // ⚠️ REFUSE RATHER THAN EMIT AN INVALID CONTAINER. Measured: an
  // `mc:AlternateContent` holding a cell's only paragraph was deleted whole and
  // left `<w:tc><w:tcPr/></w:tc>`. Recursing into that wrapper fixes the
  // measured case; this refuses the ones nobody has constructed yet.
  if (required && survivingRequired === 0) return false;
  return gapIsInvisible(xml.slice(cursor, node.endTagStart));
}

/**
 * Clear a content control by DELETING everything inside it that is not
 * structural skeleton.
 *
 * Returns `null` when the shape cannot be cleared safely (fall back, earn no
 * `emptied` proof), or the deletion patches — possibly EMPTY, meaning the
 * control already held nothing but skeleton and there was nothing to clear.
 */
/**
 * Style ids whose paragraph style carries LIVE numbering, resolved transitively
 * through `w:basedOn`.
 *
 * ⚠️ WITHOUT THIS THE NUMBERING GUARD READS THE WRONG DOCUMENT. A paragraph's
 * numbering can live entirely in `styles.xml`: the cleared region then contains
 * only `<w:pStyle w:val="ListParagraph"/>` and no `w:numPr` at all, so a search
 * of the region finds nothing. Measured to PDF — the field printed
 * `ANTICOAGULATED 1.` while proofed `emptied` and holding blank credit.
 *
 * ⚠️ `numId="0"` IS EXCLUDED, and that is not a detail. It is Word's own "no
 * list" marker — precisely what it writes when a user REMOVES numbering from a
 * paragraph whose style carries it. Treating it as numbered refuses blank
 * credit to a field that renders nothing, which is a false refusal costing a
 * doctor their certification.
 */
/**
 * What `styles.xml` says about numbering, for ONE document.
 *
 * ⚠️ RETURNED, NOT KEPT IN A MODULE-LEVEL VARIABLE. The first version stored the
 * default style id in a `let` at module scope — a cross-document contamination
 * bug in a clinical renderer: document A's default style would still be set
 * while document B, which declares none, was rendered, so B's unstyled
 * paragraphs would inherit A's numbering. Nothing in a single render reveals it.
 */
interface NumberingStyles {
  readonly numbered: ReadonlySet<string>;
  /** Id of the `w:default="1"` paragraph style; `''` when none is declared. */
  readonly defaultId: string;
}

function numberedStyleIds(pkg: ReturnType<typeof inspectDocxPackage>): NumberingStyles {
  const entry = pkg.zip.entries.get('word/styles.xml');
  if (!entry) return { numbered: new Set(), defaultId: '' };
  let scan: ScannedXmlPart;
  try {
    scan = scanXmlPart(entry.bytes);
  } catch {
    // ⚠️ FAIL-CLOSED IS NOT AVAILABLE HERE, so fail LOUD-BY-OMISSION instead:
    // an unreadable styles part means we cannot say a style is numbered, and
    // refusing every field on that basis would break every render of a document
    // whose styles we merely failed to parse. The direct `w:numPr` check still
    // applies; this only widens it.
    return { numbered: new Set(), defaultId: '' };
  }
  let defaultId = '';
  const direct = new Set<string>();
  const basedOn = new Map<string, string>();
  const styles: XmlElementSpan[] = [];
  for (const root of scan.roots) {
    styles.push(...descendantXmlElements(root, 'style'));
  }
  for (const style of styles) {
    const id = readXmlAttribute(scan.text, style, 'styleId');
    if (!id) continue;
    // ⚠️ THE DEFAULT STYLE IS AN IMPLICIT EDGE THE CLOSURE OTHERWISE MISSES.
    // A paragraph with no `w:pStyle` inherits `w:default="1"`, so numbering on
    // that style reaches a paragraph that names nothing. Measured: identical
    // `styles.xml` and identical PDF, but the paragraph naming the style was
    // refused and the one naming nothing earned `emptied` and counted.
    if (
      readXmlAttribute(scan.text, style, 'type') === 'paragraph' &&
      readXmlAttribute(scan.text, style, 'default') === '1'
    ) {
      defaultId = id;
    }
    const numbering = descendantXmlElements(style, 'numPr');
    // ⚠️ A `w:numPr` WITH NO `w:numId` IS NOT NUMBERING. It carries only an
    // `w:ilvl` — an outline level — and numbering requires a list to point at.
    // Scoring a MISSING numId as live is the opposite direction from the
    // deliberate `numId="0"` exclusion beside it, and it costs a FALSE REFUSAL:
    // Word's built-in `Subtitle` has exactly this shape, byte-identical in BOTH
    // tracked customer templates, so it is in the style table of essentially
    // every real upload.
    const live = numbering.some((numPr) => {
      const numId = descendantXmlElements(numPr, 'numId')[0];
      return numId !== undefined && readXmlAttribute(scan.text, numId, 'val') !== '0';
    });
    if (live) direct.add(id);
    const parent = directXmlChild(style, 'basedOn');
    const parentId = parent ? readXmlAttribute(scan.text, parent, 'val') : null;
    if (parentId) basedOn.set(id, parentId);
  }
  // Transitive closure over `basedOn`, bounded by the number of styles so a
  // cyclic `basedOn` chain cannot spin.
  const resolved = new Set(direct);
  for (let pass = 0; pass < basedOn.size + 1; pass += 1) {
    let grew = false;
    for (const [id, parent] of basedOn) {
      if (!resolved.has(id) && resolved.has(parent)) {
        resolved.add(id);
        grew = true;
      }
    }
    if (!grew) break;
  }
  return { numbered: resolved, defaultId };
}

/**
 * Does this paragraph carry LIVE numbering — directly, or through its style?
 *
 * ⚠️ `w:pPrChange` IS SKIPPED. It records a paragraph's FORMER properties for
 * revision history and renders nothing, so numbering inside it is a fact about
 * the document's past. Counting it refuses blank credit to a field that prints
 * nothing.
 */
function paragraphIsNumbered(
  xml: string,
  paragraph: XmlElementSpan,
  numberedStyles: NumberingStyles,
): boolean {
  const properties = directXmlChild(paragraph, 'pPr');
  // ⚠️ NO `w:pPr` IS NOT "NOT NUMBERED". A paragraph that declares nothing still
  // inherits the `w:default="1"` style, so this early return defeated the
  // default-style rule entirely — on the very shape the rule was added for.
  if (!properties) {
    return numberedStyles.defaultId !== '' &&
      numberedStyles.numbered.has(numberedStyles.defaultId);
  }
  for (const numPr of descendantXmlElements(properties, 'numPr')) {
    let ancestor: XmlElementSpan | null = numPr.parent;
    let historical = false;
    while (ancestor && ancestor !== properties) {
      if (xmlLocalName(ancestor.name) === 'pPrChange') { historical = true; break; }
      ancestor = ancestor.parent;
    }
    if (historical) continue;
    const numId = descendantXmlElements(numPr, 'numId')[0];
    // Same rule as `numberedStyleIds`: no `numId` means no list to number from.
    if (numId !== undefined && readXmlAttribute(xml, numId, 'val') !== '0') return true;
  }
  const styleRef = directXmlChild(properties, 'pStyle');
  const styleId = styleRef
    ? readXmlAttribute(xml, styleRef, 'val')
    : numberedStyles.defaultId;
  return styleId !== null && styleId !== '' && numberedStyles.numbered.has(styleId);
}

/** Control kinds whose emptied region can render a value nobody chose. */
const SELECTION_KINDS: ReadonlySet<TemplateField['kind']> = new Set([
  'single_select',
  'multi_select',
]);

interface BoundedClear {
  readonly patches: ApprovedXmlPatch[];
  /**
   * May this clear earn an `emptied` proof that COUNTS toward the certification
   * blank requirement? Separate from whether the clear happened, because #168
   * rules two cases fail-closed ON THE COUNT rather than on the render.
   */
  readonly blankEligible: boolean;
}

function sdtBoundedClearPatches(
  xml: string,
  control: XmlElementSpan,
  field: TemplateField,
  fieldId: string,
  numberedStyles: NumberingStyles,
): BoundedClear | null {
  // The control itself must hold nothing but its properties and its content.
  // A stray run directly inside `w:sdt` is malformed and is refused rather than
  // reasoned about.
  const contents: XmlElementSpan[] = [];
  for (const child of control.children) {
    const local = xmlLocalName(child.name);
    if (local === 'sdtPr' || local === 'sdtEndPr') continue;
    // ⚠️ EVERY `sdtContent` IS CLEARED, NOT JUST THE FIRST. v2's guard matched
    // by NAME, so a SECOND `w:sdtContent` passed it and survived intact —
    // rendering WARFARIN out of a control proofed `emptied`.
    if (local === 'sdtContent') {
      contents.push(child);
      continue;
    }
    return null;
  }
  if (contents.length === 0) return null;

  const out: ApprovedXmlPatch[] = [];
  for (const content of contents) {
    if (content.selfClosing) continue;
    if (!structureKeepDeletions(xml, content, fieldId, out)) return null;
  }

  // ⚠️ #168(a) — NUMBERING STAYS, BUT THE FIELD CANNOT CLAIM BLANK.
  //
  // `w:numPr` rides inside the kept-whole `w:pPr` and drives a marker from
  // `numbering.xml`. Measured: with `lvlText="ANTICOAGULATED %1."` the exported
  // PDF prints `ANTICOAGULATED 1.` for a field proofed `emptied` — arbitrary
  // template-authored text, not a bullet.
  //
  // Removing `numPr` is NOT the answer: it renumbers the doctor's list beyond
  // this field, damage outside the thing being cleared. So the numbering stays
  // and the COUNT fails closed instead — no parsing of `lvlText`, no heuristic
  // about which markers are "just" markers. If a cleared region carries
  // numbering at all, the field simply cannot claim blank.
  // ⚠️ THE SEARCH REACHES EVERY PARAGRAPH THAT COULD NUMBER THIS FIELD — the
  // ones INSIDE the control, and the one CONTAINING it.
  //
  // Scoping it to the control's own content missed both of the shapes that
  // matter. For an INLINE control the numbering sits on the `w:pPr` of the
  // paragraph HOLDING it; and for either, the numbering can live in
  // `styles.xml` behind a `w:pStyle`, so the region contains no `w:numPr` at
  // all. Both were measured printing `ANTICOAGULATED 1.` from a field proofed
  // `emptied` with blank credit — the same string, three different routes.
  //
  // `WM IOV Template.docx` has FOUR paragraphs carrying both `w:numPr` and an
  // inline `w:sdt`, masked today only because its controls are dropdowns, which
  // #168(b) denies for an unrelated reason. The owner's form — 30
  // `narrative_text` + 5 `number`, no selections — has nothing masking it.
  const paragraphs: XmlElementSpan[] = [];
  for (const content of contents) {
    paragraphs.push(...descendantXmlElements(content, 'p'));
  }
  let containing: XmlElementSpan | null = control.parent;
  while (containing && xmlLocalName(containing.name) !== 'p') {
    containing = containing.parent;
  }
  if (containing) paragraphs.push(containing);
  const numbered = paragraphs.some((paragraph) =>
    paragraphIsNumbered(xml, paragraph, numberedStyles),
  );

  // ⚠️ #168(b) — SELECTION CONTROLS ARE EXCLUDED, REVERSING #165.
  //
  // #165 included them because they clear identically at the XML level, which
  // is true and was the wrong axis. Measured on the real template: an emptied
  // dropdown makes the PDF engine fall back to `w:listItem[0]`, so
  // "Choose an item." prints while the field buys blank credit. Base printed it
  // too — so this does not create a new visual, it turns a TRUE statement into a
  // FALSE ATTESTATION, which is worse.
  //
  // The fallback itself is an EXPORT defect independent of certification and is
  // filed as its own item; this line only stops the certificate asserting a
  // blank that is not one.
  const selection = SELECTION_KINDS.has(field.kind);

  // ⚠️ ONE DELIBERATE EXCEPTION TO `sdtPr` BEING KEPT WHOLE, AND IT IS
  // MEASURED. `w:showingPlcHdr` is not an inert property: it asserts "what you
  // are looking at IS the placeholder", and Word acts on it by re-displaying
  // the template's own prompt from `w:placeholder`/`w:docPart`. Once the
  // content is deleted that assertion is false, and leaving it set is how
  // "Choose an item." reappears in a field the certificate attests as blank.
  //
  // ⚠️ EVERY `sdtPr` IN THE CONTROL, NOT JUST THE OUTER ONE. A NESTED control
  // kept its own flag AND its `w:placeholder`/`w:docPart` inside a span proofed
  // `emptied` — the same hazard this exception exists for, un-applied one level
  // down, with the blank credit now attached.
  //
  // ⚠️ AND UNCONDITIONALLY, NOT ONLY WHEN SOMETHING ELSE WAS DELETED. Gating it
  // on `out.length > 0` meant a control whose content was already pure skeleton
  // kept the flag — measured as a regression against the previous commit, which
  // removed it there.
  for (const flag of descendantXmlElements(control, 'showingPlcHdr')) {
    out.push(removeXmlElementPatch(flag, fieldId));
  }

  return { patches: out, blankEligible: !numbered && !selection };
}

/**
 * What the writer DID, reported back so the proof can be a fact about the write
 * rather than a claim about the field's kind.
 *
 * ⚠️ #164 DERIVED THE LABEL FROM A KIND BLACKLIST AND WAS WRONG THREE WAYS:
 * it excluded selections on the false premise that a null one "asserts a
 * choice" (measured: a null `single_select` clears to empty exactly like
 * narrative), its prose said "narrative" while the blacklist admitted `date`,
 * `number` and `measurement`, and it labelled repeating-row fields by omission.
 * `boundedClear` cannot drift from the write, because it IS the write.
 */
interface FieldPatchResult {
  readonly patches: ApprovedXmlPatch[];
  /** True ONLY when the clear happened AND may earn a counted `emptied` proof. */
  readonly boundedClear: boolean;
  /**
   * May this field claim blankness AT ALL — by either label?
   *
   * ⚠️ IT HAS TO LEAVE THIS FUNCTION, because a control whose content is
   * ALREADY skeleton produces ZERO patches, and the zero-patch path emits
   * `blank` unconditionally. The eligibility was computed and thrown away, so
   * two documents printing the identical list marker got opposite verdicts:
   *
   *   numbered paragraph WITH a run    -> patches -> `filled`, no credit
   *   numbered paragraph, run ALREADY gone -> none -> `blank`,  CREDIT
   *
   * The second is the first's output. And unlike the KIND, numbering cannot be
   * re-derived at the read path — the stored proof carries no numbering signal
   * — so this is the only place the decision can be made.
   */
  readonly blankEligible: boolean;
}

function contentControlPatches(
  xml: string,
  control: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
  numberedStyles: NumberingStyles,
): FieldPatchResult {
  const properties = directXmlChild(control, 'sdtPr');
  const content = directXmlChild(control, 'sdtContent');
  if (!properties || !content) failTemplateDocxRender('BINDING_NOT_FOUND');

  if (field.kind === 'checkbox') {
    const checkbox = descendantXmlElements(properties, 'checkbox')[0];
    const checked = checkbox
      ? descendantXmlElements(checkbox, 'checked')[0]
      : undefined;
    if (!checkbox || !checked) failTemplateDocxRender('BINDING_NOT_FOUND');
    if (
      resolution.value !== null &&
      typeof resolution.value !== 'boolean'
    ) {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    const selected = resolution.value === true;
    const state = selected
      ? descendantXmlElements(checkbox, 'checkedState')[0]
      : descendantXmlElements(checkbox, 'uncheckedState')[0];
    const glyph = state
      ? glyphFromWordCode(readXmlAttribute(xml, state, 'val'))
      : selected
        ? '☒'
        : '☐';
    // ⚠️ A CHECKBOX IS NEVER BOUNDED-CLEARED, AND THAT IS DELIBERATE. Both of
    // its states PRINT — `☒` and `☐` are equally visible marks — so a null
    // checkbox is not an empty field, it is an unticked one. We write the
    // unchecked glyph on purpose, so there is no clearing to prove and it must
    // never buy a blank proof. Note this now falls out of what the writer DOES,
    // rather than from a list of kinds somebody has to keep correct.
    return {
      patches: [
        setXmlAttributePatch(xml, checked, 'val', selected ? '1' : '0', field.fieldId),
        ...textContainerPatches(xml, content, glyph, field.fieldId),
      ],
      boundedClear: false,
      blankEligible: true,
    };
  }

  if (field.kind === 'date') {
    const date = directXmlChild(properties, 'date');
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
    if (resolution.value === null) {
      const cleared = sdtBoundedClearPatches(xml, control, field, field.fieldId, numberedStyles);
      if (cleared) {
        return {
          patches: [...(statePatch ? [statePatch] : []), ...cleared.patches],
          // ⚠️ AN EMPTY ARRAY IS TRUTHY. `[]` means "already empty, nothing to
          // do" — no clearing write happened, so it cannot earn `emptied`.
          boundedClear: cleared.patches.length > 0 && cleared.blankEligible,
          blankEligible: cleared.blankEligible,
        };
      }
    }
    return {
      patches: [
        ...(statePatch ? [statePatch] : []),
        ...textContainerPatches(xml, content, display, field.fieldId),
      ],
      boundedClear: false,
      blankEligible: true,
    };
  }

  if (field.kind === 'single_select') {
    const comboBox = directXmlChild(properties, 'comboBox');
    const lastValue = comboBox
      ? descendantXmlElements(comboBox, 'lastValue')[0]
      : undefined;
    if (resolution.value === null) {
      // ⚠️ SELECTIONS ARE INCLUDED — #164 EXCLUDED THEM ON A FALSE PREMISE.
      // Its comment claimed "a selection control that renders anything asserts
      // a choice". Measured: a null `single_select` renders NOTHING. It is the
      // dropdown-dominated forms (WM_IOV is 28 of them) that most need this.
      const cleared = sdtBoundedClearPatches(xml, control, field, field.fieldId, numberedStyles);
      if (cleared) {
        return {
          patches: [
            ...(lastValue ? [removeXmlElementPatch(lastValue, field.fieldId)] : []),
            ...cleared.patches,
          ],
          // ⚠️ `blankEligible` is FALSE here by construction — #168(b) excludes
          // selection kinds — so this clears the control and earns no blank
          // credit. The clearing still matters: it is what stops the previously
          // SELECTED text printing.
          boundedClear: cleared.patches.length > 0 && cleared.blankEligible,
          blankEligible: cleared.blankEligible,
        };
      }
      return {
        patches: [
          ...(lastValue ? [removeXmlElementPatch(lastValue, field.fieldId)] : []),
          ...textContainerPatches(xml, content, '', field.fieldId),
        ],
        boundedClear: false,
      blankEligible: true,
      };
    }
    const option = exactSelectedOption(field, resolution);
    return {
      patches: [
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
      ],
      boundedClear: false,
      blankEligible: true,
    };
  }

  if (resolution.value === null) {
    const cleared = sdtBoundedClearPatches(xml, control, field, field.fieldId, numberedStyles);
    if (cleared) {
      return {
        patches: cleared.patches,
        boundedClear: cleared.patches.length > 0 && cleared.blankEligible,
          blankEligible: cleared.blankEligible,
      };
    }
  }
  const display = displayValue(field, resolution);
  return {
    patches: textContainerPatches(xml, content, display, field.fieldId),
    boundedClear: false,
      blankEligible: true,
  };
}

function legacyFieldPatches(
  xml: string,
  begin: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const formData = descendantXmlElements(begin, 'ffData')[0];
  if (!formData) failTemplateDocxRender('BINDING_NOT_FOUND');
  const patches: ApprovedXmlPatch[] = [];
  const display = displayValue(field, resolution);

  if (field.kind === 'single_select') {
    const list = descendantXmlElements(formData, 'ddList')[0];
    if (!list) failTemplateDocxRender('BINDING_NOT_FOUND');
    const result = descendantXmlElements(list, 'result')[0];
    if (resolution.value === null) {
      if (result) patches.push(removeXmlElementPatch(result, field.fieldId));
    } else {
      const ordinal = exactSelectedOption(field, resolution).ordinal;
      patches.push(
        result
          ? setXmlAttributePatch(xml, result, 'val', String(ordinal), field.fieldId)
          : insertXmlChildPatch(
              xml,
              list,
              list.children.find((child) => xmlLocalName(child.name) === 'listEntry'),
              wordElement(list, 'result', ordinal),
              field.fieldId,
            ),
      );
    }
  } else if (field.kind === 'checkbox') {
    const checkbox = descendantXmlElements(formData, 'checkBox')[0];
    if (!checkbox) failTemplateDocxRender('BINDING_NOT_FOUND');
    const checked = descendantXmlElements(checkbox, 'checked')[0];
    if (
      resolution.value !== null &&
      typeof resolution.value !== 'boolean'
    ) {
      failTemplateDocxRender('FIELD_VALUE_INVALID');
    }
    const value = resolution.value === true ? '1' : '0';
    patches.push(
      checked
        ? setXmlAttributePatch(xml, checked, 'val', value, field.fieldId)
        : appendXmlChildPatch(xml, checkbox, wordElement(checkbox, 'checked', value), field.fieldId),
    );
  } else {
    const textInput = descendantXmlElements(formData, 'textInput')[0];
    if (!textInput) failTemplateDocxRender('BINDING_NOT_FOUND');
    const currentDefault = descendantXmlElements(textInput, 'default')[0];
    if (resolution.value === null) {
      if (currentDefault) {
        patches.push(removeXmlElementPatch(currentDefault, field.fieldId));
      }
    } else {
      patches.push(
        currentDefault
          ? setXmlAttributePatch(xml, currentDefault, 'val', display, field.fieldId)
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
    patches.push(...patchExistingTextNodes(xml, resultTextNodes, display, field.fieldId));
  }
  return patches;
}

function tableCellPatches(
  xml: string,
  cell: XmlElementSpan,
  field: TemplateField,
  resolution: PreparedResolution,
): ApprovedXmlPatch[] {
  const display = displayValue(field, resolution);
  const textNodes = descendantXmlElements(cell, 't');
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
      return safeDisplayText(exactSelectedOption(field, resolution).displayText);
    case 'multi_select': {
      if (!Array.isArray(resolution.value)) {
        failTemplateDocxRender('FIELD_VALUE_INVALID');
      }
      const values = resolution.value.map((value) => {
        const option = field.allowedOptions.find((candidate) => candidate.value === value);
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
      if (typeof resolution.value !== 'string' || !isStrictIsoDate(resolution.value)) {
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
        (typeof resolution.value !== 'number' || !Number.isFinite(resolution.value)) &&
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
  if (!year || !month || !day || /[A-Za-z]/.test(format.replace(/yyyy|yy|MM|M|dd|d/g, ''))) {
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
  const textNodes = descendantXmlElements(container, 't');
  if (textNodes.length === 0) failTemplateDocxRender('BINDING_NOT_FOUND');
  return patchExistingTextNodes(xml, textNodes, safeDisplayText(display), fieldId);
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
  if (xmlLocalName(node.name) !== 't') failTemplateDocxRender('BINDING_NOT_FOUND');
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
  const fieldCharacters = descendantXmlElements(paragraph, 'fldChar');
  const beginIndex = fieldCharacters.findIndex((candidate) => candidate === begin);
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
  return descendantXmlElements(paragraph, 't').filter(
    (node) => node.start >= separate!.end && node.end <= end!.start,
  );
}

/**
 * #165 RULE 2 — sha256 OF THE BINDING SPAN AS THE WRITER MEANT TO LEAVE IT.
 *
 * Ported verbatim in shape from the held #162(c) branch, whose instrument was
 * isolation-proven. Its one gap was WRITER-BLINDNESS: it faithfully compared
 * the output against the writer's own intention, so a writer that failed to
 * clear something encoded that failure into the expectation and the comparison
 * still passed. Rule 1 closes exactly that gap for SDTs — the writer can no
 * longer leave anything behind, because it replaces the whole subtree.
 *
 * Together: rule 1 makes the write correct by construction, and this makes the
 * OUTPUT provably equal to that write. Neither half is sufficient alone, which
 * is why both falsified attempts that shipped one of them failed.
 */
function expectedEmptiedSpanSha256(
  scan: ScannedXmlPart,
  field: TemplateField,
  patches: readonly ApprovedXmlPatch[],
): string {
  const span = scan.byPath.get(field.rendererBinding.path);
  if (!span) failTemplateDocxRender('BINDING_NOT_FOUND');
  const patchedPart = applyApprovedXmlPatches(scan.text, patches);
  // The span's own end shifts by whatever the patches INSIDE it changed.
  const delta = patches
    .filter((patch) => patch.start >= span.start && patch.end <= span.end)
    .reduce(
      (acc, patch) => acc + (patch.replacement.length - (patch.end - patch.start)),
      0,
    );
  return createHash('sha256')
    .update(patchedPart.slice(span.start, span.end + delta))
    .digest('hex');
}

function fieldProof(
  field: TemplateField,
  value: FieldResolution['value'],
  occurrences: number,
  kind: 'filled' | 'blank' = 'filled',
): RenderedFieldProof {
  return {
    kind,
    fieldId: field.fieldId,
    partName: field.rendererBinding.partName,
    bindingPath: field.rendererBinding.path,
    valueSha256: canonicalSha256({ fieldId: field.fieldId, value }),
    occurrences,
  };
}

/**
 * `emptied` has its OWN builder because it has its own obligation: it cannot be
 * constructed without `expectedSpanSha256`. The type system therefore refuses an
 * uncheckable emptied proof at compile time, which is a stronger guarantee than
 * the verifier's run-time refusal — and both are kept, because the proof also
 * arrives from the database on the read path where no compiler was present.
 */
function emptiedProof(
  field: TemplateField,
  value: FieldResolution['value'],
  occurrences: number,
  expectedSpanSha256: string,
): RenderedFieldProof {
  return {
    kind: 'emptied',
    fieldId: field.fieldId,
    partName: field.rendererBinding.partName,
    bindingPath: field.rendererBinding.path,
    valueSha256: canonicalSha256({ fieldId: field.fieldId, value }),
    occurrences,
    expectedSpanSha256,
  };
}
