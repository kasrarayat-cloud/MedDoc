import { createHash } from 'node:crypto';

import type { TemplateDocIR } from '../template-twin/ir';
import type { TemplateDocxLimits } from './limits';
import { inspectDocxPackage } from './package-security';

export type TemplateDocxRenderErrorCode =
  | 'SOURCE_IR_MISMATCH'
  | 'VALIDATION_REQUIRED'
  | 'FIELD_RESOLUTION_INVALID'
  | 'FIELD_VALUE_INVALID'
  | 'FIELD_VALUE_TOO_LARGE'
  | 'BINDING_NOT_FOUND'
  | 'BINDING_AMBIGUOUS'
  | 'UNSUPPORTED_BINDING'
  | 'TABLE_ROW_LIMIT_EXCEEDED'
  | 'PATCH_OVERLAP'
  | 'PACKAGE_WRITE_FAILED'
  | 'ROUNDTRIP_PACKAGE_INVALID'
  | 'ROUNDTRIP_FIELD_MISMATCH'
  | 'STATIC_INVARIANCE_FAILED';

const SAFE_RENDER_MESSAGES: Record<TemplateDocxRenderErrorCode, string> = {
  SOURCE_IR_MISMATCH:
    'The immutable source document does not match its compiled template structure.',
  VALIDATION_REQUIRED:
    'A successful independent field validation is required before rendering.',
  FIELD_RESOLUTION_INVALID:
    'The document field resolutions are incomplete or invalid.',
  FIELD_VALUE_INVALID:
    'A resolved field value cannot be represented by its approved document binding.',
  FIELD_VALUE_TOO_LARGE:
    'A resolved field value exceeds the safe Word rendering limit.',
  BINDING_NOT_FOUND:
    'An approved renderer binding was not found in the immutable source document.',
  BINDING_AMBIGUOUS:
    'An approved renderer binding is structurally ambiguous.',
  UNSUPPORTED_BINDING:
    'The template contains a renderer binding that is not supported in this version.',
  TABLE_ROW_LIMIT_EXCEEDED:
    'A repeating table exceeds its certified maximum row count.',
  PATCH_OVERLAP:
    'Two approved renderer bindings overlap and cannot be patched safely.',
  PACKAGE_WRITE_FAILED: 'The cloned Word package could not be written safely.',
  ROUNDTRIP_PACKAGE_INVALID:
    'The rendered Word package did not pass package verification.',
  ROUNDTRIP_FIELD_MISMATCH:
    'A rendered field did not match its intended approved value.',
  STATIC_INVARIANCE_FAILED:
    'Content outside the approved renderer bindings changed during rendering.',
};

/** Safe to persist or audit: no entry names, labels, or clinical values. */
export class TemplateDocxRenderError extends Error {
  readonly code: TemplateDocxRenderErrorCode;

  constructor(code: TemplateDocxRenderErrorCode, options?: { cause?: unknown }) {
    super(SAFE_RENDER_MESSAGES[code], options);
    this.name = 'TemplateDocxRenderError';
    this.code = code;
  }
}

export function failTemplateDocxRender(
  code: TemplateDocxRenderErrorCode,
): never {
  throw new TemplateDocxRenderError(code);
}

export type XmlEncoding = 'utf8' | 'utf16le' | 'utf16be';

export interface XmlElementSpan {
  readonly name: string;
  readonly path: string;
  readonly start: number;
  readonly startTagEnd: number;
  readonly endTagStart: number;
  readonly end: number;
  readonly selfClosing: boolean;
  readonly parent: XmlElementSpan | null;
  readonly children: readonly XmlElementSpan[];
}

export interface ScannedXmlPart {
  readonly text: string;
  readonly encoding: XmlEncoding;
  readonly hadBom: boolean;
  readonly roots: readonly XmlElementSpan[];
  readonly byPath: ReadonlyMap<string, XmlElementSpan>;
}

interface MutableXmlElementSpan {
  name: string;
  path: string;
  start: number;
  startTagEnd: number;
  endTagStart: number;
  end: number;
  selfClosing: boolean;
  parent: MutableXmlElementSpan | null;
  children: MutableXmlElementSpan[];
  childCounts: Map<string, number>;
}

const MAX_SCANNED_XML_ELEMENTS = 250_000;

/**
 * Locates exact raw XML spans without serializing the part. Structural paths
 * intentionally match the compiler's qualified-name sibling paths.
 */
export function scanXmlPart(bytes: Uint8Array): ScannedXmlPart {
  const decoded = decodeXmlPart(bytes);
  const roots: MutableXmlElementSpan[] = [];
  const byPath = new Map<string, MutableXmlElementSpan>();
  const stack: MutableXmlElementSpan[] = [];
  const rootCounts = new Map<string, number>();
  let cursor = 0;

  while (cursor < decoded.text.length) {
    const open = decoded.text.indexOf('<', cursor);
    if (open < 0) break;

    if (decoded.text.startsWith('<!--', open)) {
      cursor = terminatedAt(decoded.text, open + 4, '-->');
      continue;
    }
    if (decoded.text.startsWith('<![CDATA[', open)) {
      cursor = terminatedAt(decoded.text, open + 9, ']]>');
      continue;
    }
    if (decoded.text.startsWith('<?', open)) {
      cursor = terminatedAt(decoded.text, open + 2, '?>');
      continue;
    }
    if (decoded.text.startsWith('<!', open)) {
      failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    }

    const tagEnd = findTagEnd(decoded.text, open);
    const rawTag = decoded.text.slice(open, tagEnd);
    if (/^<\s*\//.test(rawTag)) {
      const name = /^<\s*\/\s*([^\s>]+)/.exec(rawTag)?.[1];
      const current = stack.pop();
      if (!name || !current || current.name !== name) {
        failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
      }
      current.endTagStart = open;
      current.end = tagEnd;
      cursor = tagEnd;
      continue;
    }

    const name = /^<\s*([^\s/>]+)/.exec(rawTag)?.[1];
    if (!name) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    const parent = stack.at(-1) ?? null;
    const counts = parent?.childCounts ?? rootCounts;
    const ordinal = counts.get(name) ?? 0;
    counts.set(name, ordinal + 1);
    const path = `${parent?.path ?? ''}/${name}[${ordinal}]`;
    if (byPath.has(path) || byPath.size >= MAX_SCANNED_XML_ELEMENTS) {
      failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    }
    const selfClosing = /\/\s*>$/.test(rawTag);
    const node: MutableXmlElementSpan = {
      name,
      path,
      start: open,
      startTagEnd: tagEnd,
      endTagStart: tagEnd,
      end: tagEnd,
      selfClosing,
      parent,
      children: [],
      childCounts: new Map(),
    };
    byPath.set(path, node);
    if (parent) parent.children.push(node);
    else roots.push(node);
    if (!selfClosing) stack.push(node);
    cursor = tagEnd;
  }

  if (stack.length > 0 || roots.length !== 1) {
    failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
  }
  return {
    ...decoded,
    roots,
    byPath,
  };
}

function terminatedAt(source: string, start: number, terminator: string): number {
  const end = source.indexOf(terminator, start);
  if (end < 0) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
  return end + terminator.length;
}

function findTagEnd(source: string, start: number): number {
  let quote: '"' | "'" | null = null;
  for (let index = start + 1; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === '>') return index + 1;
  }
  failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
}

function decodeXmlPart(bytes: Uint8Array): {
  text: string;
  encoding: XmlEncoding;
  hadBom: boolean;
} {
  const source = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (source.length >= 2 && source[0] === 0xff && source[1] === 0xfe) {
    return {
      text: source.subarray(2).toString('utf16le'),
      encoding: 'utf16le',
      hadBom: true,
    };
  }
  if (source.length >= 2 && source[0] === 0xfe && source[1] === 0xff) {
    const swapped = Buffer.from(source.subarray(2));
    swapped.swap16();
    return {
      text: swapped.toString('utf16le'),
      encoding: 'utf16be',
      hadBom: true,
    };
  }
  if (source.length >= 4 && source[0] === 0x3c && source[1] === 0x00) {
    return { text: source.toString('utf16le'), encoding: 'utf16le', hadBom: false };
  }
  if (source.length >= 4 && source[0] === 0x00 && source[1] === 0x3c) {
    const swapped = Buffer.from(source);
    swapped.swap16();
    return { text: swapped.toString('utf16le'), encoding: 'utf16be', hadBom: false };
  }
  try {
    return {
      text: new TextDecoder('utf-8', { fatal: true }).decode(source),
      encoding: 'utf8',
      hadBom: source.length >= 3 && source.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf])),
    };
  } catch (cause) {
    throw new TemplateDocxRenderError('ROUNDTRIP_PACKAGE_INVALID', { cause });
  }
}

export function encodeXmlPart(
  text: string,
  encoding: XmlEncoding,
  hadBom: boolean,
): Buffer {
  if (encoding === 'utf8') {
    const body = Buffer.from(text, 'utf8');
    return hadBom ? Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), body]) : body;
  }
  const littleEndian = Buffer.from(text, 'utf16le');
  if (encoding === 'utf16le') {
    return hadBom
      ? Buffer.concat([Buffer.from([0xff, 0xfe]), littleEndian])
      : littleEndian;
  }
  const bigEndian = Buffer.from(littleEndian);
  bigEndian.swap16();
  return hadBom
    ? Buffer.concat([Buffer.from([0xfe, 0xff]), bigEndian])
    : bigEndian;
}

export function xmlLocalName(name: string): string {
  const colon = name.indexOf(':');
  return colon < 0 ? name : name.slice(colon + 1);
}

export function directXmlChild(
  node: XmlElementSpan,
  localName: string,
): XmlElementSpan | undefined {
  return node.children.find((child) => xmlLocalName(child.name) === localName);
}

export function descendantXmlElements(
  node: XmlElementSpan,
  localName: string,
): XmlElementSpan[] {
  const result: XmlElementSpan[] = [];
  const stack = [...node.children].reverse();
  while (stack.length > 0) {
    const candidate = stack.pop()!;
    if (xmlLocalName(candidate.name) === localName) result.push(candidate);
    for (let index = candidate.children.length - 1; index >= 0; index -= 1) {
      stack.push(candidate.children[index]!);
    }
  }
  return result;
}

export interface ApprovedXmlPatch {
  readonly start: number;
  readonly end: number;
  readonly replacement: string;
  readonly fieldIds: readonly string[];
  readonly kind: 'field_content' | 'control_state' | 'repeating_row';
}

export function applyApprovedXmlPatches(
  source: string,
  patches: readonly ApprovedXmlPatch[],
): string {
  const ordered = [...patches].sort(
    (left, right) => right.start - left.start || right.end - left.end,
  );
  let previousStart = source.length + 1;
  for (const patch of ordered) {
    if (
      !Number.isSafeInteger(patch.start) ||
      !Number.isSafeInteger(patch.end) ||
      patch.start < 0 ||
      patch.end < patch.start ||
      patch.end > source.length ||
      patch.end > previousStart ||
      patch.start === previousStart
    ) {
      failTemplateDocxRender('PATCH_OVERLAP');
    }
    previousStart = patch.start;
  }

  let output = source;
  for (const patch of ordered) {
    output = `${output.slice(0, patch.start)}${patch.replacement}${output.slice(patch.end)}`;
  }
  return output;
}

/**
 * Proof that one field's rendered state is the state we approved.
 *
 * Two kinds, because there are two honest outcomes and BOTH must be attested:
 *
 *  * 'filled' — the field was patched. Verified exactly as before: its id must
 *    appear in the approved patch set. Byte-identical to the pre-blank
 *    behaviour; nothing on this path changed.
 *
 *  * 'blank'  — nothing was written, so the field keeps the doctor's own
 *    unfilled state ("Choose an item.", an empty cell). Verified by comparing
 *    the rendered bytes AT THAT BINDING against the SOURCE template's bytes at
 *    the same binding. Not "is it empty", not "does a null hash match" — is it
 *    still, byte for byte, the canvas the doctor uploaded.
 *
 * A blank field emitting no proof at all was the gap: the certification gate
 * requires one entry per expected field, so every honestly-blank field silently
 * had none and certification could not close.
 */
export type RenderedFieldProof =
  | {
      readonly kind: 'filled';
      readonly fieldId: string;
      readonly partName: string;
      readonly bindingPath: string;
      readonly valueSha256: string;
      readonly occurrences: number;
    }
  | {
      readonly kind: 'blank';
      readonly fieldId: string;
      readonly partName: string;
      readonly bindingPath: string;
      /** Hash of the approved (null) value, same shape the gate computes. */
      readonly valueSha256: string;
      /** One verified binding site. The gate requires > 0 and is untouched. */
      readonly occurrences: number;
    };

export interface RenderedPartProof {
  readonly partName: string;
  readonly patches: readonly ApprovedXmlPatch[];
}

export interface RenderVerificationPlan {
  readonly parts: readonly RenderedPartProof[];
  readonly fields: readonly RenderedFieldProof[];
}

export interface VerifiedRenderedField {
  /** Which contract this entry attests — a fill, or a proven-blank. Persisted
   *  into the roundtrip proof so the certification gate can require at least
   *  one blank-verified field. */
  readonly kind: 'filled' | 'blank';
  readonly fieldId: string;
  readonly partName: string;
  readonly bindingPath: string;
  readonly valueSha256: string;
  readonly occurrences: number;
  readonly status: 'verified';
}

export interface TemplateDocxRoundTripVerification {
  readonly verified: true;
  readonly packageCheck: 'verified';
  readonly fieldCheck: 'verified';
  readonly staticRegionCheck: 'verified';
  readonly sourceSha256: string;
  readonly outputSha256: string;
  readonly untouchedEntriesVerified: number;
  readonly modifiedPartsVerified: number;
  readonly fields: readonly VerifiedRenderedField[];
  readonly warningCodes: readonly string[];
}

export interface VerifyRenderedTemplateDocxInput {
  source: Uint8Array;
  output: Uint8Array;
  ir: TemplateDocIR;
  plan: RenderVerificationPlan;
  limits?: Partial<TemplateDocxLimits>;
}

/**
 * Reopens the generated package and proves that every decompressed OPC entry is
 * either byte-identical to the source or exactly derivable from approved
 * binding patches. Unsupported controls are never broadly masked.
 */
export function verifyRenderedTemplateDocx(
  input: VerifyRenderedTemplateDocxInput,
): TemplateDocxRoundTripVerification {
  let sourcePackage: ReturnType<typeof inspectDocxPackage>;
  let outputPackage: ReturnType<typeof inspectDocxPackage>;
  try {
    sourcePackage = inspectDocxPackage(input.source, input.limits);
    outputPackage = inspectDocxPackage(input.output, input.limits);
  } catch (cause) {
    throw new TemplateDocxRenderError('ROUNDTRIP_PACKAGE_INVALID', { cause });
  }

  if (
    sourcePackage.sourceSha256 !== input.ir.source.sha256 ||
    sourcePackage.zip.source.length !== input.ir.source.sizeBytes
  ) {
    failTemplateDocxRender('SOURCE_IR_MISMATCH');
  }

  const sourceNames = [...sourcePackage.zip.entries.keys()].sort();
  const outputNames = [...outputPackage.zip.entries.keys()].sort();
  if (
    sourceNames.length !== outputNames.length ||
    sourceNames.some((name, index) => name !== outputNames[index])
  ) {
    failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
  }

  const partProofs = new Map<string, RenderedPartProof>();
  for (const proof of input.plan.parts) {
    if (
      partProofs.has(proof.partName) ||
      !sourcePackage.zip.entries.has(proof.partName)
    ) {
      failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
    }
    partProofs.set(proof.partName, proof);
  }

  let untouchedEntriesVerified = 0;
  for (const name of sourceNames) {
    const sourceEntry = sourcePackage.zip.entries.get(name)!;
    const outputEntry = outputPackage.zip.entries.get(name)!;
    const proof = partProofs.get(name);
    if (!proof) {
      if (!sourceEntry.bytes.equals(outputEntry.bytes)) {
        failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
      }
      untouchedEntriesVerified += 1;
      continue;
    }

    const scanned = scanXmlPart(sourceEntry.bytes);
    assertPatchesWithinApprovedBindings(input.ir, proof, scanned);
    const expectedText = applyApprovedXmlPatches(scanned.text, proof.patches);
    const expectedBytes = encodeXmlPart(
      expectedText,
      scanned.encoding,
      scanned.hadBom,
    );
    if (!expectedBytes.equals(outputEntry.bytes)) {
      failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
    }
    // A second parser pass detects malformed spans or unbalanced XML even when
    // the ZIP/OPC layer itself is valid.
    scanXmlPart(outputEntry.bytes);
  }
  const proofFieldIds = new Set<string>();
  const filledFieldIds = new Set<string>();
  const blankProofs: RenderedFieldProof[] = [];
  for (const field of input.plan.fields) {
    if (proofFieldIds.has(field.fieldId) || field.occurrences < 1) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    proofFieldIds.add(field.fieldId);
    if (field.kind === 'blank') blankProofs.push(field);
    else filledFieldIds.add(field.fieldId);
  }
  const patchedFieldIds = new Set(
    input.plan.parts.flatMap((part) =>
      part.patches.flatMap((patch) => patch.fieldIds),
    ),
  );
  // FILLED: unchanged — the filled proof set must be exactly the patched set.
  if (
    filledFieldIds.size !== patchedFieldIds.size ||
    [...filledFieldIds].some((fieldId) => !patchedFieldIds.has(fieldId))
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  // BLANK: a blank field must not appear in the patch set at all — claiming a
  // field is blank while having patched it is the contradiction worth catching.
  for (const blank of blankProofs) {
    if (patchedFieldIds.has(blank.fieldId)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
  }
  // ...and the rendered bytes at its binding must still BE the source's bytes.
  // Same failure class as a filled mismatch: a blank is a claim about the
  // document, and an unverified claim is exactly what this module exists to
  // prevent.
  if (blankProofs.length > 0) {
    const sourceScans = new Map<string, ScannedXmlPart>();
    const outputScans = new Map<string, ScannedXmlPart>();
    const scanOf = (
      cache: Map<string, ScannedXmlPart>,
      pkg: typeof sourcePackage,
      partName: string,
    ): ScannedXmlPart => {
      const hit = cache.get(partName);
      if (hit) return hit;
      const entry = pkg.zip.entries.get(partName);
      if (!entry) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      const scanned = scanXmlPart(entry.bytes);
      cache.set(partName, scanned);
      return scanned;
    };
    for (const blank of blankProofs) {
      const src = scanOf(sourceScans, sourcePackage, blank.partName);
      const out = scanOf(outputScans, outputPackage, blank.partName);
      const srcSpan = src.byPath.get(blank.bindingPath);
      const outSpan = out.byPath.get(blank.bindingPath);
      if (!srcSpan || !outSpan) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      const srcBytes = src.text.slice(srcSpan.start, srcSpan.end);
      const outBytes = out.text.slice(outSpan.start, outSpan.end);
      if (srcBytes !== outBytes) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
  }

  const outputSha256 = createHash('sha256')
    .update(Buffer.from(input.output))
    .digest('hex');
  // OOXML has no authoritative rendered-page geometry; only Word (or another
  // layout engine with the template fonts) can prove visual overflow. Flag the
  // two deterministic risk signals we can detect without pretending to have
  // performed layout: a replacement far larger than its original binding and
  // cloned repeating rows. Certification/review can then inspect the DOCX.
  const warningCodes = new Set<string>();
  for (const part of input.plan.parts) {
    for (const patch of part.patches) {
      const originalLength = Math.max(1, patch.end - patch.start);
      if (
        patch.kind === 'field_content' &&
        patch.replacement.length > 512 &&
        patch.replacement.length > originalLength * 4
      ) {
        warningCodes.add('LAYOUT_OVERFLOW_REVIEW_RECOMMENDED');
      }
      if (patch.kind === 'repeating_row') {
        warningCodes.add('REPEATING_TABLE_LAYOUT_REVIEW_RECOMMENDED');
      }
    }
  }
  return Object.freeze({
    verified: true,
    packageCheck: 'verified',
    fieldCheck: 'verified',
    staticRegionCheck: 'verified',
    sourceSha256: sourcePackage.sourceSha256,
    outputSha256,
    untouchedEntriesVerified,
    modifiedPartsVerified: partProofs.size,
    fields: input.plan.fields.map((field) => ({
      ...field,
      status: 'verified' as const,
    })),
    warningCodes: [...warningCodes].sort(),
  });
}

function assertPatchesWithinApprovedBindings(
  ir: TemplateDocIR,
  part: RenderedPartProof,
  scanned: ScannedXmlPart,
): void {
  const fields = new Map(ir.fields.map((field) => [field.fieldId, field]));
  for (const patch of part.patches) {
    if (patch.fieldIds.length === 0) {
      failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
    }
    for (const fieldId of patch.fieldIds) {
      const field = fields.get(fieldId);
      if (
        !field ||
        field.detectionStatus === 'unsupported' ||
        field.rendererBinding.partName !== part.partName
      ) {
        failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
      }

      let allowed = scanned.byPath.get(field.rendererBinding.path);
      if (patch.kind === 'repeating_row') {
        if (!field.rowPrototype || !field.rendererBinding.repeatAncestorPath) {
          failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
        }
        allowed = scanned.byPath.get(field.rendererBinding.repeatAncestorPath);
      } else if (field.rendererBinding.bindingType === 'legacy_form_field') {
        while (allowed && xmlLocalName(allowed.name) !== 'p') {
          allowed = allowed.parent ?? undefined;
        }
      }
      if (
        !allowed ||
        patch.start < allowed.start ||
        patch.end > allowed.end
      ) {
        failTemplateDocxRender('STATIC_INVARIANCE_FAILED');
      }
    }
  }
}
