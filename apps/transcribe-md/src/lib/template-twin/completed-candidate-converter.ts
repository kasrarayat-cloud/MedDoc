import { createHash } from "node:crypto";

import JSZip from "jszip";

import {
  compileTemplateDocx,
  inspectDocxPackage,
} from "@/lib/note-template-docx";
import {
  applyApprovedXmlPatches,
  descendantWordElements,
  directWordChild,
  encodeXmlPart,
  scanXmlPart,
  wordVisibleText,
  xmlLocalName,
  type ApprovedXmlPatch,
  type ScannedXmlPart,
  type XmlElementSpan,
} from "@/lib/note-template-docx/roundtrip-verify";
import { detectStructuredPhi } from "@/lib/note-template-parse/phi-gate";

import { canonicalSha256 } from "./canonical";
import {
  CompletedCandidateReviewProjectionSchema,
  type CompletedCandidateReviewProjection,
} from "./completed-candidate-contract";

export const COMPLETED_CANDIDATE_CONVERTER_VERSION =
  "completed-document-candidate/1.1.0" as const;
export const COMPLETED_CANDIDATE_SYNTHETIC_SENTINEL =
  "QUILLMD SYNTHETIC EXAMPLE — NO REAL PATIENT DATA" as const;

const FIXED_ZIP_DATE = new Date("1980-01-01T00:00:00.000Z");
const SYNTHETIC_MARKER_RE =
  /\b(?:synthetic|fictional|mock(?:ed)?|test[- ]?only|example)\b/iu;
const SAFE_LABEL_RE = /^[\p{L}][\p{L}\p{M}0-9 /(),.'+\-&]{1,119}:?$/u;
const SUPPORTED_PACKAGE_PART_RE =
  /^(?:\[Content_Types\]\.xml|_rels\/\.rels|docProps\/(?:app|core|custom)\.xml|word\/(?:document|styles|numbering|settings|webSettings|fontTable)\.xml|word\/_rels\/document\.xml\.rels|word\/theme\/theme[1-9][0-9]{0,3}\.xml)$/iu;

export type CompletedCandidateFailureCode =
  | "EXAMPLE_COUNT_UNSUPPORTED"
  | "AUXILIARY_PART_UNSUPPORTED"
  | "HEADER_FOOTER_UNSUPPORTED"
  | "EXISTING_TEMPLATE_BINDINGS"
  | "SYNTHETIC_SENTINEL_REQUIRED"
  | "POSSIBLE_IDENTIFYING_CONTENT"
  | "STRUCTURE_MISMATCH"
  | "REPEATING_STRUCTURE_UNSUPPORTED"
  | "AMBIGUOUS_NARRATIVE_CHANGE"
  | "AMBIGUOUS_TABLE_CHANGE"
  | "DUPLICATE_LABEL_AMBIGUOUS"
  | "STRUCTURAL_PREVIEW_UNSUPPORTED"
  | "NO_DETERMINISTIC_REGIONS"
  | "CANDIDATE_GENERATION_FAILED";

const SAFE_MESSAGES: Record<CompletedCandidateFailureCode, string> = {
  EXAMPLE_COUNT_UNSUPPORTED:
    "Completed-document conversion requires two or three synthetic examples of the same Word layout.",
  AUXILIARY_PART_UNSUPPORTED:
    "This completed document contains media or an auxiliary Word part that the candidate workflow cannot isolate safely.",
  HEADER_FOOTER_UNSUPPORTED:
    "Completed-document conversion does not yet support headers or footers. Remove them from synthetic examples or use a blank template.",
  EXISTING_TEMPLATE_BINDINGS:
    "This document already contains a fillable control or placeholder. Use the blank or fillable template workflow.",
  SYNTHETIC_SENTINEL_REQUIRED:
    "Each example must be explicitly marked as QuillMD synthetic test data and contain no real patient information.",
  POSSIBLE_IDENTIFYING_CONTENT:
    "A local privacy check found possible identifying content. The examples remain isolated and were not converted.",
  STRUCTURE_MISMATCH:
    "The examples do not have one identical Word structure, so their changing regions cannot be located deterministically.",
  REPEATING_STRUCTURE_UNSUPPORTED:
    "A table row or cell shape changes across examples. Repeating-row inference is not supported in this candidate version.",
  AMBIGUOUS_NARRATIVE_CHANGE:
    "Narrative text changes across examples. Ordinary narrative is never assumed to be fillable.",
  AMBIGUOUS_TABLE_CHANGE:
    "A changing table value is not an unambiguous scalar cell beside one stable label.",
  DUPLICATE_LABEL_AMBIGUOUS:
    "Two changing regions use the same label. Rename them in the synthetic examples before conversion.",
  STRUCTURAL_PREVIEW_UNSUPPORTED:
    "This document has too many tables, rows, cells, or merged columns for a complete safe comparison. Simplify the synthetic examples before conversion.",
  NO_DETERMINISTIC_REGIONS:
    "No deterministic changing scalar regions were found across the synthetic examples.",
  CANDIDATE_GENERATION_FAILED:
    "The new blank candidate did not compile to the exact detected field inventory.",
};

export class CompletedCandidateConversionError extends Error {
  readonly code: CompletedCandidateFailureCode;

  constructor(code: CompletedCandidateFailureCode, cause?: unknown) {
    super(SAFE_MESSAGES[code], { cause });
    this.name = "CompletedCandidateConversionError";
    this.code = code;
  }
}

export interface CompletedCandidateExampleInput {
  /** Metadata-minimized bytes. The immutable raw upload remains in quarantine. */
  readonly document: Uint8Array;
  readonly minimizedSha256: string;
}

export interface CompletedCandidateRegion {
  readonly regionId: string;
  readonly displayOrder: number;
  readonly label: string;
  readonly evidenceType: "stable_label_changed_scalar_cell";
  readonly partName: "word/document.xml";
  readonly tableIndex: number;
  readonly rowIndex: number;
  readonly cellIndex: number;
  readonly candidateTag: string;
  readonly candidateSdtId: string;
  readonly sourceEvidenceSha256: string;
  readonly sourceDescription: string;
  readonly candidateDescription: string;
}

export interface CompletedCandidateComparison {
  readonly exampleCount: number;
  readonly identicalStructure: true;
  readonly sourceBlockCount: number;
  readonly candidateFieldCount: number;
  readonly preservedStaticBlockCount: number;
  readonly sourceSummary: string;
  readonly candidateSummary: string;
}

export interface CompletedCandidatePrivacyEvidence {
  readonly profileVersion: "completed-candidate-local-synthetic-privacy/1.1.0";
  readonly providerEgress: false;
  readonly exampleCount: number;
  readonly sentinelVerified: true;
  readonly structuredIdentifierClasses: readonly [];
  readonly sourceBinding: "minimized-package-structure-visible-text-digests";
  readonly exampleEvidenceSha256s: readonly string[];
  readonly evidenceSha256: string;
}

export interface CompletedCandidateConversionResult {
  readonly document: Buffer;
  readonly candidateSha256: string;
  readonly candidateStructureSha256: string;
  readonly inventorySha256: string;
  readonly converterVersion: typeof COMPLETED_CANDIDATE_CONVERTER_VERSION;
  readonly regions: readonly CompletedCandidateRegion[];
  readonly comparison: CompletedCandidateComparison;
  readonly reviewProjection: CompletedCandidateReviewProjection;
  readonly reviewProjectionSha256: string;
  readonly privacyEvidence: CompletedCandidatePrivacyEvidence;
  readonly exampleStructureSha256: string;
}

interface TextBlock {
  readonly key: string;
  readonly kind: "paragraph" | "table_cell";
  readonly text: string;
  readonly span: XmlElementSpan;
  readonly tableIndex: number | null;
  readonly rowIndex: number | null;
  readonly cellIndex: number | null;
}

interface InspectedExample {
  readonly document: Buffer;
  readonly packagePartsSha256: string;
  readonly documentStructureSha256: string;
  readonly blocks: readonly TextBlock[];
  readonly scan: ScannedXmlPart;
  readonly tableShape: readonly (readonly number[])[];
  readonly localPrivacyEvidenceSha256: string;
}

function sha256(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function normalizeText(value: string): string {
  return value.replace(/\s+/gu, " ").trim();
}

function directWordChildren(
  node: XmlElementSpan,
  localName: string,
): XmlElementSpan[] {
  return node.children.filter(
    (child) =>
      child.namespaceUri ===
        "http://schemas.openxmlformats.org/wordprocessingml/2006/main" &&
      xmlLocalName(child.name) === localName,
  );
}

function hasAncestor(node: XmlElementSpan, localName: string): boolean {
  let parent = node.parent;
  while (parent) {
    if (xmlLocalName(parent.name) === localName) return true;
    parent = parent.parent;
  }
  return false;
}

function packagePartsSha256(
  inspected: ReturnType<typeof inspectDocxPackage>,
): string {
  return canonicalSha256(
    [...inspected.zip.entries]
      .filter(
        ([name]) =>
          ![
            "word/document.xml",
            "docProps/core.xml",
            "docProps/app.xml",
            "docProps/custom.xml",
          ].includes(name),
      )
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, entry]) => ({ name, sha256: sha256(entry.bytes) })),
  );
}

function documentStructureSha256(scan: ScannedXmlPart): string {
  return canonicalSha256(
    [...scan.byPath.values()].map((node) => ({
      name: node.name,
      namespaceUri: node.namespaceUri,
      path: node.path,
      selfClosing: node.selfClosing,
      startTag:
        xmlLocalName(node.name) === "t"
          ? node.name
          : scan.text.slice(node.start, node.startTagEnd),
    })),
  );
}

function assertSupportedPackage(
  inspected: ReturnType<typeof inspectDocxPackage>,
): void {
  if (
    inspected.headerPartNames.length > 0 ||
    inspected.footerPartNames.length > 0
  ) {
    throw new CompletedCandidateConversionError("HEADER_FOOTER_UNSUPPORTED");
  }
  for (const name of inspected.zip.entries.keys()) {
    if (!SUPPORTED_PACKAGE_PART_RE.test(name)) {
      throw new CompletedCandidateConversionError("AUXILIARY_PART_UNSUPPORTED");
    }
  }
}

function assertSyntheticVisibleText(blocks: readonly TextBlock[]): void {
  const visible = blocks.map((block) => block.text).filter(Boolean);
  if (!visible.includes(COMPLETED_CANDIDATE_SYNTHETIC_SENTINEL)) {
    throw new CompletedCandidateConversionError("SYNTHETIC_SENTINEL_REQUIRED");
  }
  if (detectStructuredPhi(visible.join("\n")).length > 0) {
    throw new CompletedCandidateConversionError("POSSIBLE_IDENTIFYING_CONTENT");
  }

  // Synthetic-only release slice: every free-text block must say that it is
  // synthetic. The only exception is a short table label immediately used as
  // structural evidence. This intentionally rejects ordinary completed
  // reports until the human privacy/provider gates authorize a broader mode.
  for (const block of blocks) {
    if (!block.text) continue;
    if (SYNTHETIC_MARKER_RE.test(block.text)) continue;
    const hasAdjacentValueCell =
      block.kind === "table_cell" &&
      block.cellIndex !== null &&
      blocks.some(
        (candidate) =>
          candidate.kind === "table_cell" &&
          candidate.tableIndex === block.tableIndex &&
          candidate.rowIndex === block.rowIndex &&
          candidate.cellIndex === block.cellIndex! + 1,
      );
    if (hasAdjacentValueCell && SAFE_LABEL_RE.test(block.text)) continue;
    throw new CompletedCandidateConversionError("SYNTHETIC_SENTINEL_REQUIRED");
  }
}

function inspectExample(
  input: CompletedCandidateExampleInput,
  ordinal: number,
): InspectedExample {
  const inspected = inspectDocxPackage(input.document);
  assertSupportedPackage(inspected);
  if (inspected.sourceSha256 !== input.minimizedSha256) {
    throw new CompletedCandidateConversionError("STRUCTURE_MISMATCH");
  }
  const preexisting = compileTemplateDocx(input.document);
  if (preexisting.fields.length > 0 || preexisting.unsupported.length > 0) {
    throw new CompletedCandidateConversionError("EXISTING_TEMPLATE_BINDINGS");
  }

  const entry = inspected.zip.entries.get("word/document.xml");
  if (!entry) throw new CompletedCandidateConversionError("STRUCTURE_MISMATCH");
  const scan = scanXmlPart(entry.bytes);
  const root = scan.roots[0]!;
  const tables = descendantWordElements(root, "tbl");
  if (tables.some((table) => hasAncestor(table, "tc"))) {
    throw new CompletedCandidateConversionError(
      "REPEATING_STRUCTURE_UNSUPPORTED",
    );
  }

  const blocks: TextBlock[] = [];
  for (const paragraph of descendantWordElements(root, "p")) {
    if (hasAncestor(paragraph, "tc")) continue;
    blocks.push({
      key: `paragraph:${paragraph.path}`,
      kind: "paragraph",
      text: normalizeText(wordVisibleText(scan.text, paragraph)),
      span: paragraph,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
    });
  }

  const tableShape: number[][] = [];
  tables.forEach((table, tableIndex) => {
    const rows = directWordChildren(table, "tr");
    tableShape.push(rows.map((row) => directWordChildren(row, "tc").length));
    rows.forEach((row, rowIndex) => {
      directWordChildren(row, "tc").forEach((cell, cellIndex) => {
        blocks.push({
          key: `table:${tableIndex}:${rowIndex}:${cellIndex}:${cell.path}`,
          kind: "table_cell",
          text: normalizeText(wordVisibleText(scan.text, cell)),
          span: cell,
          tableIndex,
          rowIndex,
          cellIndex,
        });
      });
    });
  });
  assertSyntheticVisibleText(blocks);

  const minimizedSha256 = inspected.sourceSha256;
  const partsSha256 = packagePartsSha256(inspected);
  const structureSha256 = documentStructureSha256(scan);
  const privacyReceipt = {
    profileVersion: "completed-candidate-local-synthetic-privacy/1.1.0",
    ordinal,
    providerEgress: false,
    minimizedSha256,
    packagePartsSha256: partsSha256,
    documentStructureSha256: structureSha256,
    visibleTextSha256: sha256(
      blocks
        .map((block) => block.text)
        .filter(Boolean)
        .join("\n"),
    ),
    sentinelVerified: true,
    structuredIdentifierClasses: [] as const,
  } as const;

  return {
    document: Buffer.from(input.document),
    packagePartsSha256: partsSha256,
    documentStructureSha256: structureSha256,
    blocks,
    scan,
    tableShape,
    localPrivacyEvidenceSha256: canonicalSha256(privacyReceipt),
  };
}

interface ScalarCellShape {
  readonly paragraph: XmlElementSpan;
  readonly runPropertiesXml: string;
}

function wordAttribute(
  scan: ScannedXmlPart,
  node: XmlElementSpan,
  localName: "val" | "w",
): string | null {
  const tag = scan.text.slice(node.start, node.startTagEnd);
  const expression = new RegExp(
    `\\b(?:[A-Za-z_][\\w.-]*:)?${localName}\\s*=\\s*["']([^"']+)["']`,
    "u",
  );
  return expression.exec(tag)?.[1] ?? null;
}

function positiveWordInteger(
  scan: ScannedXmlPart,
  node: XmlElementSpan,
  localName: "val" | "w",
): number {
  const raw = wordAttribute(scan, node, localName);
  const value = raw ? Number.parseInt(raw, 10) : Number.NaN;
  if (!Number.isInteger(value) || value < 1) {
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  return value;
}

function cellColumnSpan(scan: ScannedXmlPart, cell: XmlElementSpan): number {
  const cellProperties = directWordChild(cell, "tcPr");
  if (!cellProperties) return 1;
  if (
    directWordChild(cellProperties, "vMerge") ||
    directWordChild(cellProperties, "hMerge")
  ) {
    // The first candidate release does not pretend to render a merge it cannot
    // prove exactly. Bounded horizontal gridSpan is handled explicitly below.
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  const gridSpan = directWordChild(cellProperties, "gridSpan");
  if (!gridSpan) return 1;
  const value = positiveWordInteger(scan, gridSpan, "val");
  if (value > 64) {
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  return value;
}

function tableGridBasisPoints(
  scan: ScannedXmlPart,
  table: XmlElementSpan,
): readonly number[] {
  const grid = directWordChild(table, "tblGrid");
  const columns = grid ? directWordChildren(grid, "gridCol") : [];
  if (columns.length < 1 || columns.length > 64) {
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  const widths = columns.map((column) =>
    positiveWordInteger(scan, column, "w"),
  );
  const total = widths.reduce((sum, width) => sum + width, 0);
  const basisPoints = widths.map((width) =>
    Math.floor((width * 10_000) / total),
  );
  if (basisPoints.some((width) => width < 1)) {
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  let remainder = 10_000 - basisPoints.reduce((sum, width) => sum + width, 0);
  for (let index = 0; remainder > 0; index = (index + 1) % basisPoints.length) {
    basisPoints[index]! += 1;
    remainder -= 1;
  }
  return Object.freeze(basisPoints);
}

function assertCandidateControlAtCell(input: {
  scan: ScannedXmlPart;
  cell: XmlElementSpan;
  region: CompletedCandidateRegion;
}): void {
  const controls = descendantWordElements(input.cell, "sdt");
  if (controls.length !== 1) {
    throw new CompletedCandidateConversionError("CANDIDATE_GENERATION_FAILED");
  }
  const properties = directWordChild(controls[0]!, "sdtPr");
  const tag = properties ? directWordChild(properties, "tag") : undefined;
  if (
    !tag ||
    wordAttribute(input.scan, tag, "val") !== input.region.candidateTag
  ) {
    throw new CompletedCandidateConversionError("CANDIDATE_GENERATION_FAILED");
  }
}

function buildReviewProjection(input: {
  sourceScan: ScannedXmlPart;
  candidateScan: ScannedXmlPart;
  sourceExampleSha256s: readonly string[];
  candidateSha256: string;
  candidateStructureSha256: string;
  inventorySha256: string;
  regions: readonly CompletedCandidateRegion[];
}): CompletedCandidateReviewProjection {
  const sourceBody = directWordChild(input.sourceScan.roots[0]!, "body");
  const candidateBody = directWordChild(input.candidateScan.roots[0]!, "body");
  if (!sourceBody || !candidateBody) {
    throw new CompletedCandidateConversionError("CANDIDATE_GENERATION_FAILED");
  }
  const sourceBlocks = sourceBody.children.filter((child) =>
    ["p", "tbl"].includes(xmlLocalName(child.name)),
  );
  const candidateBlocks = candidateBody.children.filter((child) =>
    ["p", "tbl"].includes(xmlLocalName(child.name)),
  );
  if (
    sourceBlocks.length !== candidateBlocks.length ||
    sourceBlocks.some(
      (block, index) =>
        xmlLocalName(block.name) !== xmlLocalName(candidateBlocks[index]!.name),
    )
  ) {
    throw new CompletedCandidateConversionError("CANDIDATE_GENERATION_FAILED");
  }
  const regionByCell = new Map(
    input.regions.map((region) => [
      `${region.tableIndex}:${region.rowIndex}:${region.cellIndex}`,
      region,
    ]),
  );
  const labelByCell = new Map(
    input.regions.map((region) => [
      `${region.tableIndex}:${region.rowIndex}:${region.cellIndex - 1}`,
      region,
    ]),
  );
  let tableIndex = 0;
  let totalRows = 0;
  let totalCells = 0;
  const blocks = sourceBlocks.map((sourceBlock, displayOrder) => {
    const candidateBlock = candidateBlocks[displayOrder]!;
    if (xmlLocalName(sourceBlock.name) === "p") {
      return Object.freeze({
        kind: "redacted_paragraph" as const,
        blockKey: `paragraph:${sourceBlock.path}`,
        displayOrder,
      });
    }
    const currentTableIndex = tableIndex;
    tableIndex += 1;
    const sourceGrid = tableGridBasisPoints(input.sourceScan, sourceBlock);
    const candidateGrid = tableGridBasisPoints(
      input.candidateScan,
      candidateBlock,
    );
    if (canonicalSha256(sourceGrid) !== canonicalSha256(candidateGrid)) {
      throw new CompletedCandidateConversionError(
        "CANDIDATE_GENERATION_FAILED",
      );
    }
    const sourceRows = directWordChildren(sourceBlock, "tr");
    const candidateRows = directWordChildren(candidateBlock, "tr");
    if (sourceRows.length < 1 || sourceRows.length !== candidateRows.length) {
      throw new CompletedCandidateConversionError(
        "CANDIDATE_GENERATION_FAILED",
      );
    }
    const rows = sourceRows.map((sourceRow, rowIndex) => {
      totalRows += 1;
      const sourceCells = directWordChildren(sourceRow, "tc");
      const candidateCells = directWordChildren(candidateRows[rowIndex]!, "tc");
      if (
        sourceCells.length < 1 ||
        sourceCells.length > 64 ||
        sourceCells.length !== candidateCells.length
      ) {
        throw new CompletedCandidateConversionError(
          "CANDIDATE_GENERATION_FAILED",
        );
      }
      let columnStart = 0;
      const cells = sourceCells.map((sourceCell, cellIndex) => {
        totalCells += 1;
        const candidateCell = candidateCells[cellIndex]!;
        const columnSpan = cellColumnSpan(input.sourceScan, sourceCell);
        if (
          columnSpan !== cellColumnSpan(input.candidateScan, candidateCell) ||
          columnStart + columnSpan > sourceGrid.length
        ) {
          throw new CompletedCandidateConversionError(
            "CANDIDATE_GENERATION_FAILED",
          );
        }
        const key = `${currentTableIndex}:${rowIndex}:${cellIndex}`;
        const region = regionByCell.get(key);
        const labelRegion = labelByCell.get(key);
        if (descendantWordElements(sourceCell, "sdt").length > 0) {
          throw new CompletedCandidateConversionError(
            "CANDIDATE_GENERATION_FAILED",
          );
        }
        if (region) {
          assertCandidateControlAtCell({
            scan: input.candidateScan,
            cell: candidateCell,
            region,
          });
        } else if (descendantWordElements(candidateCell, "sdt").length > 0) {
          throw new CompletedCandidateConversionError(
            "CANDIDATE_GENERATION_FAILED",
          );
        }
        const role = region
          ? Object.freeze({
              kind: "candidate_region" as const,
              regionId: region.regionId,
              candidateTag: region.candidateTag,
              controlKind: "plain_text" as const,
              sourceState: "VALUE_WITHHELD" as const,
              candidateState: "BLANK_CONTROL" as const,
            })
          : labelRegion
            ? Object.freeze({
                kind: "stable_label" as const,
                label: labelRegion.label,
                forRegionId: labelRegion.regionId,
              })
            : Object.freeze({ kind: "static_redacted" as const });
        const projected = Object.freeze({
          cellKey: `table:${currentTableIndex}:row:${rowIndex}:cell:${cellIndex}`,
          cellIndex,
          columnStart,
          columnSpan,
          rowSpan: 1 as const,
          role,
        });
        columnStart += columnSpan;
        return projected;
      });
      if (columnStart !== sourceGrid.length) {
        throw new CompletedCandidateConversionError(
          "STRUCTURAL_PREVIEW_UNSUPPORTED",
        );
      }
      return Object.freeze({ rowIndex, cells: Object.freeze(cells) });
    });
    return Object.freeze({
      kind: "table" as const,
      blockKey: `table:${currentTableIndex}:${sourceBlock.path}`,
      displayOrder,
      tableIndex: currentTableIndex,
      gridColumnBasisPoints: sourceGrid,
      rows: Object.freeze(rows),
    });
  });
  if (
    tableIndex < 1 ||
    tableIndex > 40 ||
    totalRows > 500 ||
    totalCells > 2_000
  ) {
    throw new CompletedCandidateConversionError(
      "STRUCTURAL_PREVIEW_UNSUPPORTED",
    );
  }
  return CompletedCandidateReviewProjectionSchema.parse({
    profileVersion:
      "completed-candidate-redacted-structural-review/1.0.0" as const,
    valuesRedacted: true as const,
    sourceBytesReturned: false as const,
    providerEgress: false as const,
    paginationRepresented: false as const,
    sourceExampleSha256s: [...input.sourceExampleSha256s],
    sourceStructureSha256: documentStructureSha256(input.sourceScan),
    candidateStructureSha256: input.candidateStructureSha256,
    inventorySha256: input.inventorySha256,
    candidateSha256: input.candidateSha256,
    blocks,
    regionCount: input.regions.length,
  });
}

function assertScalarCellShape(
  cell: XmlElementSpan,
  scan: ScannedXmlPart,
): ScalarCellShape {
  const paragraphs = directWordChildren(cell, "p");
  if (paragraphs.length !== 1) {
    throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
  }
  const paragraph = paragraphs[0]!;
  const runs = directWordChildren(paragraph, "r");
  if (runs.length !== 1) {
    // Joining multiple runs would require a judgment about formatting and
    // field boundaries. Completed-document conversion never makes it.
    throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
  }
  for (const child of paragraph.children) {
    const local = xmlLocalName(child.name);
    if (child.namespaceUri === paragraph.namespaceUri && local === "pPr") {
      continue;
    }
    if (child.namespaceUri !== paragraph.namespaceUri || local !== "r") {
      throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
    }
    for (const runChild of child.children) {
      const runLocal = xmlLocalName(runChild.name);
      if (
        runChild.namespaceUri !== paragraph.namespaceUri ||
        (runLocal !== "rPr" && runLocal !== "t")
      ) {
        throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
      }
    }
  }
  const run = runs[0]!;
  const runChildren = run.children.filter(
    (child) => child.namespaceUri === paragraph.namespaceUri,
  );
  const textNodes = runChildren.filter(
    (child) => xmlLocalName(child.name) === "t",
  );
  const runProperties = runChildren.filter(
    (child) => xmlLocalName(child.name) === "rPr",
  );
  if (
    textNodes.length !== 1 ||
    textNodes[0]!.children.length !== 0 ||
    runProperties.length > 1 ||
    (runProperties.length === 1 && runChildren[0] !== runProperties[0]) ||
    runChildren.at(-1) !== textNodes[0]
  ) {
    throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
  }
  return Object.freeze({
    paragraph,
    runPropertiesXml: runProperties[0]
      ? scan.text.slice(runProperties[0].start, runProperties[0].end)
      : "",
  });
}

function stableRegion(input: {
  label: string;
  block: TextBlock;
  values: readonly string[];
  displayOrder: number;
}): CompletedCandidateRegion {
  const identity = sha256(
    [
      COMPLETED_CANDIDATE_CONVERTER_VERSION,
      "word/document.xml",
      input.block.span.path,
      input.label,
    ].join("\0"),
  );
  const sdtNumeric =
    (Number.parseInt(identity.slice(0, 8), 16) % 2_147_483_646) + 1;
  return Object.freeze({
    regionId: `tccr_${identity.slice(0, 24)}`,
    displayOrder: input.displayOrder,
    label: input.label.replace(/:$/u, ""),
    evidenceType: "stable_label_changed_scalar_cell",
    partName: "word/document.xml",
    tableIndex: input.block.tableIndex!,
    rowIndex: input.block.rowIndex!,
    cellIndex: input.block.cellIndex!,
    candidateTag: `qmd:candidate:${identity.slice(0, 24)}`,
    candidateSdtId: String(sdtNumeric),
    sourceEvidenceSha256: canonicalSha256({
      contractVersion: COMPLETED_CANDIDATE_CONVERTER_VERSION,
      label: input.label,
      location: {
        tableIndex: input.block.tableIndex,
        rowIndex: input.block.rowIndex,
        cellIndex: input.block.cellIndex,
      },
      valueDigests: input.values.map(sha256),
    }),
    sourceDescription: `Values differed across ${input.values.length} synthetic examples beside one stable label.`,
    candidateDescription:
      "Blank Word text control with a stable QuillMD binding.",
  });
}

function detectRegions(examples: readonly InspectedExample[]): {
  regions: CompletedCandidateRegion[];
  scalarShapes: Map<string, ScalarCellShape>;
} {
  const primary = examples[0]!;
  const blocksByExample = examples.map(
    (example) => new Map(example.blocks.map((block) => [block.key, block])),
  );
  const primaryByLocation = new Map(
    primary.blocks
      .filter((block) => block.kind === "table_cell")
      .map((block) => [
        `${block.tableIndex}:${block.rowIndex}:${block.cellIndex}`,
        block,
      ]),
  );
  const regions: CompletedCandidateRegion[] = [];
  const scalarShapes = new Map<string, ScalarCellShape>();
  const labels = new Set<string>();

  for (const block of primary.blocks) {
    const values = blocksByExample.map((byKey) => byKey.get(block.key)?.text);
    if (values.some((value) => value === undefined)) {
      throw new CompletedCandidateConversionError("STRUCTURE_MISMATCH");
    }
    const texts = values as string[];
    if (new Set(texts).size === 1) continue;
    if (block.kind === "paragraph") {
      throw new CompletedCandidateConversionError("AMBIGUOUS_NARRATIVE_CHANGE");
    }
    if (
      block.cellIndex === null ||
      block.cellIndex < 1 ||
      texts.some((value) => !value || !SYNTHETIC_MARKER_RE.test(value))
    ) {
      throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
    }
    const cellIndex = block.cellIndex;
    const labelBlocks = examples.map((example) => {
      const map = new Map(
        example.blocks
          .filter((candidate) => candidate.kind === "table_cell")
          .map((candidate) => [
            `${candidate.tableIndex}:${candidate.rowIndex}:${candidate.cellIndex}`,
            candidate,
          ]),
      );
      return map.get(`${block.tableIndex}:${block.rowIndex}:${cellIndex - 1}`);
    });
    const label = labelBlocks[0]?.text ?? "";
    if (
      !label ||
      !SAFE_LABEL_RE.test(label) ||
      labelBlocks.some((candidate) => candidate?.text !== label)
    ) {
      throw new CompletedCandidateConversionError("AMBIGUOUS_TABLE_CHANGE");
    }
    const normalizedLabel = label.replace(/:$/u, "").toLocaleLowerCase();
    if (labels.has(normalizedLabel)) {
      throw new CompletedCandidateConversionError("DUPLICATE_LABEL_AMBIGUOUS");
    }
    labels.add(normalizedLabel);
    const primaryCell = primaryByLocation.get(
      `${block.tableIndex}:${block.rowIndex}:${cellIndex}`,
    );
    if (!primaryCell) {
      throw new CompletedCandidateConversionError("STRUCTURE_MISMATCH");
    }
    const scalarShape = assertScalarCellShape(primaryCell.span, primary.scan);
    const region = stableRegion({
      label,
      block: primaryCell,
      values: texts,
      displayOrder: regions.length,
    });
    regions.push(region);
    scalarShapes.set(region.regionId, scalarShape);
  }
  if (regions.length === 0) {
    throw new CompletedCandidateConversionError("NO_DETERMINISTIC_REGIONS");
  }
  return { regions, scalarShapes };
}

function escapeXmlAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function contentControlXml(
  paragraph: XmlElementSpan,
  region: CompletedCandidateRegion,
  runPropertiesXml: string,
): string {
  const prefix = paragraph.name.includes(":")
    ? `${paragraph.name.slice(0, paragraph.name.indexOf(":"))}:`
    : "";
  const w = (name: string) => `${prefix}${name}`;
  const alias = escapeXmlAttribute(region.label);
  const tag = escapeXmlAttribute(region.candidateTag);
  return `<${w("sdt")}><${w("sdtPr")}><${w("alias")} ${w("val")}="${alias}"/><${w("tag")} ${w("val")}="${tag}"/><${w("id")} ${w("val")}="${region.candidateSdtId}"/><${w("text")}/></${w("sdtPr")}><${w("sdtContent")}><${w("r")}>${runPropertiesXml}<${w("t")}></${w("t")}></${w("r")}></${w("sdtContent")}></${w("sdt")}>`;
}

async function generateCandidate(input: {
  primary: InspectedExample;
  regions: readonly CompletedCandidateRegion[];
  scalarShapes: ReadonlyMap<string, ScalarCellShape>;
}): Promise<Buffer> {
  const patches: ApprovedXmlPatch[] = input.regions.map((region) => {
    const scalarShape = input.scalarShapes.get(region.regionId);
    if (!scalarShape) {
      throw new CompletedCandidateConversionError(
        "CANDIDATE_GENERATION_FAILED",
      );
    }
    const { paragraph, runPropertiesXml } = scalarShape;
    const properties = directWordChild(paragraph, "pPr");
    return {
      start: properties?.end ?? paragraph.startTagEnd,
      end: paragraph.endTagStart,
      replacement: contentControlXml(paragraph, region, runPropertiesXml),
      fieldIds: [region.regionId],
      kind: "field_content" as const,
    };
  });
  const patchedText = applyApprovedXmlPatches(input.primary.scan.text, patches);
  const patchedDocument = encodeXmlPart(
    patchedText,
    input.primary.scan.encoding,
    input.primary.scan.hadBom,
  );
  scanXmlPart(patchedDocument);

  const zip = await JSZip.loadAsync(input.primary.document, {
    checkCRC32: true,
    createFolders: false,
  });
  zip.file("word/document.xml", patchedDocument, {
    binary: true,
    createFolders: false,
    date: FIXED_ZIP_DATE,
  });
  for (const entry of Object.values(zip.files)) {
    entry.date = FIXED_ZIP_DATE;
    entry.comment = "";
  }
  return zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
    platform: "DOS",
    streamFiles: false,
    comment: "",
  });
}

export async function convertCompletedDocumentsToCandidate(
  inputs: readonly CompletedCandidateExampleInput[],
): Promise<CompletedCandidateConversionResult> {
  if (inputs.length < 2 || inputs.length > 3) {
    throw new CompletedCandidateConversionError("EXAMPLE_COUNT_UNSUPPORTED");
  }
  const examples = inputs.map((input, index) =>
    inspectExample(input, index + 1),
  );
  const primary = examples[0]!;
  for (const example of examples.slice(1)) {
    if (
      canonicalSha256(example.tableShape) !==
      canonicalSha256(primary.tableShape)
    ) {
      throw new CompletedCandidateConversionError(
        "REPEATING_STRUCTURE_UNSUPPORTED",
      );
    }
    if (
      example.packagePartsSha256 !== primary.packagePartsSha256 ||
      example.documentStructureSha256 !== primary.documentStructureSha256
    ) {
      throw new CompletedCandidateConversionError("STRUCTURE_MISMATCH");
    }
  }

  const { regions, scalarShapes } = detectRegions(examples);
  let document: Buffer;
  try {
    document = await generateCandidate({ primary, regions, scalarShapes });
    const compiled = compileTemplateDocx(document);
    const tags = new Set(regions.map((region) => region.candidateTag));
    if (
      compiled.fields.length !== regions.length ||
      compiled.stats.blockingUnsupported !== 0 ||
      compiled.fields.some(
        (field) =>
          field.rendererBinding.bindingType !== "content_control" ||
          !field.rendererBinding.tag ||
          !tags.has(field.rendererBinding.tag),
      )
    ) {
      throw new CompletedCandidateConversionError(
        "CANDIDATE_GENERATION_FAILED",
      );
    }
    const candidateSha256 = sha256(document);
    const inventorySha256 = canonicalSha256(regions);
    const candidatePackage = inspectDocxPackage(document);
    const candidateDocumentPart =
      candidatePackage.zip.entries.get("word/document.xml");
    if (!candidateDocumentPart) {
      throw new CompletedCandidateConversionError(
        "CANDIDATE_GENERATION_FAILED",
      );
    }
    const candidateScan = scanXmlPart(candidateDocumentPart.bytes);
    const reviewProjection = buildReviewProjection({
      sourceScan: primary.scan,
      candidateScan,
      sourceExampleSha256s: inputs.map((input) => input.minimizedSha256),
      candidateSha256,
      candidateStructureSha256: compiled.structureSha256,
      inventorySha256,
      regions,
    });
    const reviewProjectionSha256 = canonicalSha256(reviewProjection);
    const comparison: CompletedCandidateComparison = Object.freeze({
      exampleCount: examples.length,
      identicalStructure: true,
      sourceBlockCount: primary.blocks.length,
      candidateFieldCount: regions.length,
      preservedStaticBlockCount: primary.blocks.length - regions.length,
      sourceSummary: `${examples.length} isolated synthetic examples with one identical Word structure. Example values are withheld.`,
      candidateSummary: `${regions.length} changed labeled scalar regions were blanked into stable Word text controls.`,
    });
    const privacyReceipt = {
      profileVersion:
        "completed-candidate-local-synthetic-privacy/1.1.0" as const,
      providerEgress: false as const,
      exampleCount: examples.length,
      sentinelVerified: true as const,
      structuredIdentifierClasses: [] as const,
      sourceBinding:
        "minimized-package-structure-visible-text-digests" as const,
      exampleEvidenceSha256s: examples.map(
        (example) => example.localPrivacyEvidenceSha256,
      ),
    };
    return Object.freeze({
      document,
      candidateSha256,
      candidateStructureSha256: compiled.structureSha256,
      inventorySha256,
      converterVersion: COMPLETED_CANDIDATE_CONVERTER_VERSION,
      regions: Object.freeze(regions),
      comparison,
      reviewProjection,
      reviewProjectionSha256,
      privacyEvidence: Object.freeze({
        ...privacyReceipt,
        evidenceSha256: canonicalSha256(privacyReceipt),
      }),
      exampleStructureSha256: primary.documentStructureSha256,
    });
  } catch (error) {
    if (error instanceof CompletedCandidateConversionError) throw error;
    throw new CompletedCandidateConversionError(
      "CANDIDATE_GENERATION_FAILED",
      error,
    );
  }
}
