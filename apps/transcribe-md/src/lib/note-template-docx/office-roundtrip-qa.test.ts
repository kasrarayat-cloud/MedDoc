import JSZip from "jszip";
import { beforeAll, describe, expect, it } from "vitest";

import { canonicalSha256 } from "../template-twin/canonical";
import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from "../template-twin/ir";
import { buildSyntheticDocx } from "./__tests__/synthetic-docx";
import {
  TAB_ONLY_OFFICE_FIELD_LABEL,
  TAB_ONLY_OFFICE_FIELD_VALUE,
  buildTabOnlyTableCellOfficeCorpusDocx,
} from "./__tests__/tab-only-office-corpus";
import { compileTemplateDocx } from "./compiler";
import { readbackTemplateDocxOutput } from "./output-readback";
import { renderTemplateDocx } from "./renderer";
import {
  OFFICE_PDF_VISUAL_METRICS_CONTRACT_VERSION,
  OFFICE_EXECUTION_EVIDENCE_CONTRACT_VERSION,
  OFFICE_PINNED_APPLICATION_NAME,
  OFFICE_PINNED_APPLICATION_VERSION,
  OFFICE_PINNED_IMAGE,
  OFFICE_PINNED_IMAGE_DIGEST,
  buildOfficeExpectedValueManifest,
  buildOfficeVisibleStaticManifest,
  hashOfficePdfVisualMetricsEvidence,
  hashOfficeExecutionEvidence,
  hashPreOfficeRendererReadbackV2Evidence,
  inspectOfficeDocxSecurityQa,
  normalizeOfficeVisibleStaticText,
  readOfficeSavedDocxFieldsQa,
  sha256OfficeDocxBytes,
  verifyOfficeRoundTripQa,
  type OfficeExpectedValueManifest,
  type OfficeExecutionEvidence,
  type OfficePdfVisualMetricsEvidence,
  type VerifyOfficeRoundTripQaInput,
} from "./office-roundtrip-qa";
import {
  OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION,
  evaluateOfficeSchemaEvidence,
  type EvaluateOfficeSchemaEvidenceInput,
  type OfficeSchemaArtifactStage,
  type OfficeSchemaDiagnosticEvidence,
  type OfficeSchemaQaResult,
} from "./office-schema-evidence";

const sha = (value: unknown): string => canonicalSha256(value);
const FACT_ID = `ttfact_${"a".repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: "2026-07-16T00:00:00.000Z",
  validatorVersion: "template-field-validator/1.0.0",
};
const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <w:body>
  <w:p><w:r><w:t>Synthetic narrative: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="501"/><w:tag w:val="qa_text"/><w:alias w:val="Synthetic narrative"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter value</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Synthetic category: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="502"/><w:tag w:val="qa_category"/><w:alias w:val="Synthetic category"/><w:dropDownList><w:listItem w:displayText="Alpha" w:value="alpha"/><w:listItem w:displayText="Beta" w:value="beta"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Synthetic severity: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="503"/><w:tag w:val="qa_severity"/><w:alias w:val="Synthetic severity"/><w:comboBox><w:listItem w:displayText="Mild" w:value="mild"/><w:listItem w:displayText="Severe" w:value="severe"/></w:comboBox></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Synthetic date: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="504"/><w:tag w:val="qa_date"/><w:alias w:val="Synthetic date"/><w:date><w:dateFormat w:val="yyyy-MM-dd"/><w:lid w:val="en-US"/><w:storeMappedDataAs w:val="dateTime"/><w:calendar w:val="gregorian"/></w:date></w:sdtPr><w:sdtContent><w:r><w:t>Pick a date.</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Synthetic reviewed: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="505"/><w:tag w:val="qa_reviewed"/><w:alias w:val="Synthetic reviewed"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Legacy reviewed: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy synthetic check"/><w:checkBox><w:default w:val="0"/><w:checked w:val="1"/></w:checkBox></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMCHECKBOX </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>☒</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
  <w:p><w:r><w:t>Legacy category: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy synthetic category"/><w:ddList><w:result w:val="1"/><w:listEntry w:val="Alpha"/><w:listEntry w:val="Beta"/><w:listEntry w:val="Gamma"/></w:ddList></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Beta</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
  <w:p><w:r><w:t>Legacy note: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy synthetic note"/><w:textInput><w:type w:val="regular"/><w:default w:val="Synthetic legacy note"/><w:maxLength w:val="32767"/></w:textInput></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Synthetic legacy note</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
  <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
 </w:body>
</w:document>`;

interface Fixture {
  source: Buffer;
  ir: TemplateDocIR;
  resolutions: FieldResolution[];
  rendererOutput: Buffer;
  officeSaved: Buffer;
  expected: OfficeExpectedValueManifest;
}

let fixture: Fixture;

function valueFor(
  field: TemplateField,
): [FieldResolution["value"], number | null] {
  const values: Record<string, [FieldResolution["value"], number | null]> = {
    "Synthetic narrative": [
      "Synthetic stable value & XML-safe <evidence>",
      null,
    ],
    "Synthetic category": ["beta", 1],
    "Synthetic severity": ["mild", 0],
    "Synthetic date": ["2026-07-16", null],
    "Synthetic reviewed": [true, null],
    "Legacy synthetic check": [true, null],
    "Legacy synthetic category": ["Beta", 1],
    "Legacy synthetic note": ["Synthetic legacy note", null],
    "Practice display name": ["Synthetic Practice", null],
  };
  const value = values[field.originalLabel];
  if (!value)
    throw new Error(`Unexpected synthetic field ${field.originalLabel}`);
  return value;
}

function resolution(field: TemplateField): FieldResolution {
  const [value, selectedOptionOrdinal] = valueFor(field);
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: "supported",
    value,
    sourceFactIds: [FACT_ID],
    evidenceAnchorIds: ["synthetic-office-anchor"],
    selectedOptionOrdinal,
    reasonCode: "synthetic_office_evidence",
    clinicianReviewed: false,
  });
}

beforeAll(async () => {
  const source = await buildSyntheticDocx({ documentXml: DOCUMENT_XML });
  const ir = compileTemplateDocx(source);
  const resolutions = ir.fields.map(resolution);
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  const expected = buildOfficeExpectedValueManifest({
    syntheticOnly: true,
    sourceDocxBytes: source,
    rendererOutputDocxBytes: rendered.document,
    ir,
    resolutions,
  });
  const officeSaved = await mutatePackagePart(
    rendered.document,
    "[Content_Types].xml",
    (xml) => xml.replace("</Types>", "  \n</Types>"),
  );
  fixture = {
    source,
    ir,
    resolutions,
    rendererOutput: rendered.document,
    officeSaved,
    expected,
  };
});

async function fixtureForResolutions(
  resolutions: readonly FieldResolution[],
): Promise<Fixture> {
  const rendered = await renderTemplateDocx({
    source: fixture.source,
    ir: fixture.ir,
    resolutions,
    validation: VALIDATION,
  });
  const expected = buildOfficeExpectedValueManifest({
    syntheticOnly: true,
    sourceDocxBytes: fixture.source,
    rendererOutputDocxBytes: rendered.document,
    ir: fixture.ir,
    resolutions,
  });
  const officeSaved = await mutatePackagePart(
    rendered.document,
    "[Content_Types].xml",
    (xml) => xml.replace("</Types>", "  \n</Types>"),
  );
  return {
    source: fixture.source,
    ir: fixture.ir,
    resolutions: [...resolutions],
    rendererOutput: rendered.document,
    officeSaved,
    expected,
  };
}

async function tabOnlyTableCellFixture(
  value: string | null = TAB_ONLY_OFFICE_FIELD_VALUE,
): Promise<Fixture> {
  const source = await buildTabOnlyTableCellOfficeCorpusDocx();
  const ir = compileTemplateDocx(source);
  const field = ir.fields.find(
    (candidate) => candidate.originalLabel === TAB_ONLY_OFFICE_FIELD_LABEL,
  );
  if (!field || ir.fields.length !== 1) {
    throw new Error(
      "Synthetic tab-only Office field was not uniquely admitted.",
    );
  }
  const resolutions = [
    FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: value === null ? "not_mentioned" : "supported",
      value,
      sourceFactIds: value === null ? [] : [FACT_ID],
      evidenceAnchorIds:
        value === null ? [] : ["synthetic-tab-only-office-anchor"],
      selectedOptionOrdinal: null,
      reasonCode:
        value === null
          ? "synthetic_tab_only_office_not_mentioned"
          : "synthetic_tab_only_office_evidence",
      clinicianReviewed: true,
    }),
  ];
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  const expected = buildOfficeExpectedValueManifest({
    syntheticOnly: true,
    sourceDocxBytes: source,
    rendererOutputDocxBytes: rendered.document,
    ir,
    resolutions,
  });
  const officeSaved = await mutatePackagePart(
    rendered.document,
    "[Content_Types].xml",
    (xml) => xml.replace("</Types>", "  \n</Types>"),
  );
  return {
    source,
    ir,
    resolutions,
    rendererOutput: rendered.document,
    officeSaved,
    expected,
  };
}

async function ordinaryPlaceholderFixture(): Promise<Fixture> {
  const source = await buildSyntheticDocx({
    documentXml: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>
<w:p><w:r><w:t>Synthetic finding: [[fi</w:t></w:r><w:r><w:t>nding]]</w:t></w:r></w:p>
<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/></w:sectPr></w:body></w:document>`,
    extraEntries: {
      "word/header1.xml": `<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic static header</w:t></w:r></w:p></w:hdr>`,
      "word/footer1.xml": `<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic static footer</w:t></w:r></w:p></w:ftr>`,
    },
  });
  const ir = compileTemplateDocx(source);
  const field = ir.fields.find(
    (candidate) =>
      candidate.rendererBinding.bindingType === "ordinary_placeholder",
  );
  if (!field || ir.fields.length !== 1) {
    throw new Error(
      "Synthetic ordinary placeholder was not uniquely admitted.",
    );
  }
  const resolutions = [
    FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: "supported",
      value: "Synthetic stable finding",
      sourceFactIds: [FACT_ID],
      evidenceAnchorIds: ["synthetic-ordinary-office-anchor"],
      selectedOptionOrdinal: null,
      reasonCode: "synthetic_ordinary_office_evidence",
      clinicianReviewed: true,
    }),
  ];
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  const expected = buildOfficeExpectedValueManifest({
    syntheticOnly: true,
    sourceDocxBytes: source,
    rendererOutputDocxBytes: rendered.document,
    ir,
    resolutions,
  });
  const officeSaved = await mutateDocument(rendered.document, (xml) =>
    xml
      .replace(
        "<w:p><w:r><w:t>Synthetic finding: Synthetic stable finding</w:t></w:r><w:r><w:t></w:t></w:r></w:p>",
        "<w:p><w:r><w:t>Synthetic finding: Synthetic stable finding</w:t></w:r></w:p>",
      )
      .replace(
        'w:header="720" w:footer="720"/>',
        'w:header="720" w:footer="720" w:gutter="0"/>',
      ),
  );
  return {
    source,
    ir,
    resolutions,
    rendererOutput: rendered.document,
    officeSaved,
    expected,
  };
}

function mutateSdtWithId(
  xml: string,
  nativeId: string,
  mutate: (controlXml: string) => string,
): string {
  const marker = `<w:id w:val="${nativeId}"`;
  const markerOffset = xml.indexOf(marker);
  const start = xml.lastIndexOf("<w:sdt>", markerOffset);
  const end = xml.indexOf("</w:sdt>", markerOffset) + "</w:sdt>".length;
  if (markerOffset < 0 || start < 0 || end < "</w:sdt>".length) {
    throw new Error(`Synthetic SDT ${nativeId} missing.`);
  }
  const before = xml.slice(start, end);
  const after = mutate(before);
  if (after === before) throw new Error("Synthetic SDT mutation was a no-op.");
  return `${xml.slice(0, start)}${after}${xml.slice(end)}`;
}

function mutateLegacyFieldWithName(
  xml: string,
  legacyName: string,
  mutate: (paragraphXml: string) => string,
): string {
  const marker = `<w:name w:val="${legacyName}"`;
  const markerOffset = xml.indexOf(marker);
  const start = xml.lastIndexOf("<w:p>", markerOffset);
  const end = xml.indexOf("</w:p>", markerOffset) + "</w:p>".length;
  if (markerOffset < 0 || start < 0 || end < "</w:p>".length) {
    throw new Error(`Synthetic legacy field ${legacyName} missing.`);
  }
  const before = xml.slice(start, end);
  const after = mutate(before);
  if (after === before) {
    throw new Error("Synthetic legacy mutation was a no-op.");
  }
  return `${xml.slice(0, start)}${after}${xml.slice(end)}`;
}

async function mutateDocument(
  bytes: Uint8Array,
  mutate: (xml: string) => string,
): Promise<Buffer> {
  return mutatePackagePart(bytes, "word/document.xml", mutate);
}

async function mutatePackagePart(
  bytes: Uint8Array,
  partName: string,
  mutate: (xml: string) => string,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(bytes);
  const entry = zip.file(partName);
  if (!entry) throw new Error(`Synthetic package part missing: ${partName}.`);
  const before = await entry.async("string");
  const after = mutate(before);
  if (after === before) throw new Error("Synthetic mutation was a no-op.");
  zip.file(partName, after);
  return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
}

function reviewerProvenance() {
  return {
    reviewerId: "synthetic-independent-auditor",
    reviewerRole: "independent_office_release_auditor" as const,
    reviewedAt: "2026-07-16T00:00:00.000Z",
    reviewRecordSha256: sha("synthetic-reviewed-schema-registry"),
    registryVersion: OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION,
  };
}

function schemaStage(
  stage: OfficeSchemaArtifactStage,
  artifactId: string,
  artifactSha256: string,
  diagnostics: readonly OfficeSchemaDiagnosticEvidence[] = [],
  targetFormat = "Office2013",
) {
  return {
    stage,
    targetFormat,
    validatorName: "DocumentFormat.OpenXml.OpenXmlValidator",
    validatorVersion: "3.5.1.0",
    executionLogSha256: sha(`execution:${stage}:${targetFormat}`),
    artifacts: [
      {
        artifactId,
        artifactSha256,
        opened: true,
        reportedDiagnosticCount: diagnostics.length,
        validatorLogSha256: sha(
          `validator:${stage}:${targetFormat}:${artifactId}`,
        ),
        diagnostics,
      },
    ],
  } as const;
}

function schemaInput(
  officeBytes: Uint8Array,
  officeDiagnostics: readonly OfficeSchemaDiagnosticEvidence[] = [],
  currentFixture: Fixture = fixture,
): EvaluateOfficeSchemaEvidenceInput {
  const officeSha = sha256OfficeDocxBytes(officeBytes);
  const targets = ["Office2013", "Microsoft365"] as const;
  return {
    syntheticOnly: true,
    reviewerProvenance: reviewerProvenance(),
    requiredStages: targets.flatMap((targetFormat) => [
      { stage: "source" as const, targetFormat, artifactIds: ["source.docx"] },
      {
        stage: "renderer_output" as const,
        targetFormat,
        artifactIds: ["renderer.docx"],
      },
      {
        stage: "office_saved" as const,
        targetFormat,
        artifactIds: ["office-saved.docx"],
      },
    ]),
    stages: targets.flatMap((targetFormat) => [
      schemaStage(
        "source",
        "source.docx",
        currentFixture.expected.sourceDocxSha256,
        [],
        targetFormat,
      ),
      schemaStage(
        "renderer_output",
        "renderer.docx",
        currentFixture.expected.rendererOutputDocxSha256,
        [],
        targetFormat,
      ),
      schemaStage(
        "office_saved",
        "office-saved.docx",
        officeSha,
        officeDiagnostics,
        targetFormat,
      ),
    ]),
  };
}

function schemaFor(
  officeBytes: Uint8Array,
  officeDiagnostics: readonly OfficeSchemaDiagnosticEvidence[] = [],
  currentFixture: Fixture = fixture,
): OfficeSchemaQaResult {
  return evaluateOfficeSchemaEvidence(
    schemaInput(officeBytes, officeDiagnostics, currentFixture),
  );
}

function rehashSchema(
  schema: OfficeSchemaQaResult,
  mutate: (
    unsigned: Omit<OfficeSchemaQaResult, "evidenceSha256">,
  ) => Omit<OfficeSchemaQaResult, "evidenceSha256">,
): OfficeSchemaQaResult {
  const { evidenceSha256: originalEvidenceSha256, ...unsigned } = schema;
  expect(originalEvidenceSha256).toMatch(/^[a-f0-9]{64}$/);
  const changed = mutate(unsigned);
  return {
    ...changed,
    evidenceSha256: canonicalSha256(changed),
  };
}

function rehashSchemaMatrixRow(
  row: OfficeSchemaQaResult["matrix"][number],
  change: Partial<OfficeSchemaQaResult["matrix"][number]>,
): OfficeSchemaQaResult["matrix"][number] {
  const changed = { ...row, ...change };
  const { matrixId: ignoredMatrixId, ...withoutId } = changed;
  expect(ignoredMatrixId).toBeTruthy();
  return {
    ...withoutId,
    matrixId: `office_schema_${canonicalSha256(withoutId).slice(0, 24)}`,
  };
}

function visibleStatic(docxSha256: string, normalizedPartNames = false) {
  return buildOfficeVisibleStaticManifest({
    syntheticOnly: true,
    docxSha256,
    regions: [
      {
        logicalRegionId: "main-static",
        role: "main_document",
        partName: "word/document.xml",
        visibleTokens: ["Synthetic labels remain unchanged"],
        structuralTokens: ["five-paragraphs", "section-properties"],
      },
      {
        logicalRegionId: "header-default",
        role: "header",
        partName: normalizedPartNames ? "word/header2.xml" : "word/header1.xml",
        visibleTokens: ["Synthetic header"],
        structuralTokens: ["single-paragraph"],
      },
    ],
  });
}

function visualFor(
  officeBytes: Uint8Array,
  currentFixture: Fixture = fixture,
): OfficePdfVisualMetricsEvidence {
  const officeSavedDocxSha256 = sha256OfficeDocxBytes(officeBytes);
  const unsigned = {
    contractVersion: OFFICE_PDF_VISUAL_METRICS_CONTRACT_VERSION,
    syntheticOnly: true as const,
    rendererName: "Poppler pdftoppm",
    rendererVersion: "25.12.0",
    executionLogSha256: sha("synthetic-visual-execution-log"),
    dpi: 144,
    rendererOutputDocxSha256: currentFixture.expected.rendererOutputDocxSha256,
    officeSavedDocxSha256,
    originalPdfSourceDocxSha256:
      currentFixture.expected.rendererOutputDocxSha256,
    roundTripPdfSourceDocxSha256: officeSavedDocxSha256,
    originalPdfSha256: sha("synthetic-original-pdf"),
    roundTripPdfSha256: sha("synthetic-roundtrip-pdf"),
    originalPageCount: 1,
    roundTripPageCount: 1,
    pages: [
      {
        pageNumber: 1,
        originalWidthPixels: 1224,
        originalHeightPixels: 1584,
        roundTripWidthPixels: 1224,
        roundTripHeightPixels: 1584,
        originalHeaderSha256: sha("header-pixels"),
        roundTripHeaderSha256: sha("header-pixels"),
        originalFooterSha256: sha("footer-pixels"),
        roundTripFooterSha256: sha("footer-pixels"),
        originalMaskedStaticSha256: sha("masked-static-pixels"),
        roundTripMaskedStaticSha256: sha("masked-static-pixels"),
        differingPixels: 0,
        totalPixels: 1_938_816,
        maximumChannelDifference: 0,
        approvedFieldMaskSha256: sha("empty-approved-field-mask"),
        approvedFieldRegionCount: 0,
        differenceClassification: "none" as const,
        humanReviewed: false,
      },
    ],
  };
  return {
    ...unsigned,
    evidenceSha256: hashOfficePdfVisualMetricsEvidence(unsigned),
  };
}

function executionFor(
  officeBytes: Uint8Array,
  visualMetrics: OfficePdfVisualMetricsEvidence,
  currentFixture: Fixture = fixture,
): OfficeExecutionEvidence {
  const officeSavedDocxSha256 = sha256OfficeDocxBytes(officeBytes);
  const command = (
    stage: OfficeExecutionEvidence["commands"][number]["stage"],
    inputArtifactSha256: string | null,
    outputArtifactSha256: string | null,
  ) => ({
    stage,
    commandSha256: sha(`office-command:${stage}`),
    stdoutSha256: sha(`office-stdout:${stage}`),
    stderrSha256: sha(`office-stderr:${stage}`),
    inputArtifactSha256,
    outputArtifactSha256,
    exitCode: 0 as const,
    succeeded: true as const,
  });
  const unsigned = {
    contractVersion: OFFICE_EXECUTION_EVIDENCE_CONTRACT_VERSION,
    syntheticOnly: true as const,
    evidenceClass: "QA_ONLY_OFFICE_COMPATIBILITY_EVIDENCE" as const,
    applicationName: OFFICE_PINNED_APPLICATION_NAME,
    applicationVersion: OFFICE_PINNED_APPLICATION_VERSION,
    image: OFFICE_PINNED_IMAGE,
    imageDigest: OFFICE_PINNED_IMAGE_DIGEST,
    networkMode: "none" as const,
    sourceMountedReadOnly: true as const,
    separateOutputPaths: true as const,
    isolatedProfilePathSha256: sha("office-path:profile"),
    sourcePathSha256: sha("office-path:source"),
    savedDocxPathSha256: sha("office-path:saved-docx"),
    rendererPdfPathSha256: sha("office-path:renderer-pdf"),
    officeSavedPdfPathSha256: sha("office-path:saved-pdf"),
    rendererOutputDocxSha256: currentFixture.expected.rendererOutputDocxSha256,
    rendererOutputSizeBytes: currentFixture.expected.rendererOutputSizeBytes,
    officeSavedDocxSha256,
    officeSavedSizeBytes: officeBytes.byteLength,
    rendererPdfSha256: visualMetrics.originalPdfSha256,
    officeSavedPdfSha256: visualMetrics.roundTripPdfSha256,
    repairOrCorruptionDiagnosticCount: 0 as const,
    warningCount: 0,
    executionLogSha256: sha("office-complete-execution-log"),
    commands: [
      command("version_probe", null, null),
      command(
        "open_save_docx",
        currentFixture.expected.rendererOutputDocxSha256,
        officeSavedDocxSha256,
      ),
      command(
        "export_renderer_pdf",
        currentFixture.expected.rendererOutputDocxSha256,
        visualMetrics.originalPdfSha256,
      ),
      command(
        "export_office_saved_pdf",
        officeSavedDocxSha256,
        visualMetrics.roundTripPdfSha256,
      ),
    ],
  };
  return {
    ...unsigned,
    evidenceSha256: hashOfficeExecutionEvidence(unsigned),
  };
}

function preOfficeReadbackV2For(currentFixture: Fixture = fixture) {
  const unsigned = {
    verificationContractVersion: "template-docx-readback/2.0.0" as const,
    status: "passed" as const,
    rendererOutputDocxSha256: currentFixture.expected.rendererOutputDocxSha256,
    rendererOutputSizeBytes: currentFixture.expected.rendererOutputSizeBytes,
    irStructureSha256: currentFixture.ir.structureSha256,
    expectedManifestSha256: currentFixture.expected.manifestSha256,
    strictVerificationEvidenceSha256: sha(
      `strict-v2:${currentFixture.expected.rendererOutputDocxSha256}`,
    ),
  };
  return {
    ...unsigned,
    evidenceSha256: hashPreOfficeRendererReadbackV2Evidence(unsigned),
  };
}

function validInput(
  officeBytes: Uint8Array = fixture.officeSaved,
  schemaEvidence: OfficeSchemaQaResult | undefined = undefined,
  currentFixture: Fixture = fixture,
): VerifyOfficeRoundTripQaInput {
  const visualMetrics = visualFor(officeBytes, currentFixture);
  return {
    syntheticOnly: true,
    certifiedIr: currentFixture.ir,
    expectedValues: currentFixture.expected,
    rendererOutputDocxBytes: currentFixture.rendererOutput,
    officeSavedDocxBytes: officeBytes,
    schemaEvidence:
      schemaEvidence ?? schemaFor(officeBytes, [], currentFixture),
    officeExecutionEvidence: executionFor(
      officeBytes,
      visualMetrics,
      currentFixture,
    ),
    visualMetrics,
    preOfficeRendererReadbackV2Evidence: preOfficeReadbackV2For(currentFixture),
    postOfficeSavedReadbackV2Status: "failed",
  };
}

function classifiedExternalDiagnostics(
  count = 42,
): OfficeSchemaDiagnosticEvidence[] {
  return Array.from({ length: count }, (_, index) => {
    const common = {
      diagnosticId: `diagnostic-${index + 1}`,
      validatorErrorId: "Sch_AttributeValueDataTypeDetailed",
      severity: "error" as const,
      disposition: "external_tool_pending_word" as const,
      descriptionSha256: sha(`description-${index}`),
      classificationRationaleSha256: sha(`rationale-${index}`),
      pathSha256: sha(`path-${index}`),
    };
    if (index < 20) {
      return {
        ...common,
        familyCode: "FONT_CHARACTER_SET_EXTENSION",
        partName: "/word/fontTable.xml",
        elementQName: "w:charset",
        attributeQName: "w:characterSet",
        observedValue: index < 12 ? "utf-8" : "windows-1252",
      };
    }
    if (index < 39) {
      return {
        ...common,
        familyCode: "LOGICAL_ALIGNMENT_ENUM",
        partName: index < 38 ? "/word/numbering.xml" : "/word/document.xml",
        elementQName: index < 38 ? "w:lvlJc" : "w:jc",
        attributeQName: "w:val",
        observedValue: "start",
      };
    }
    return {
      ...common,
      familyCode: "TABLE_ROW_ON_OFF_LEXICAL_VALUE",
      partName: "/word/document.xml",
      elementQName: index === 41 ? "w:tblHeader" : "w:cantSplit",
      attributeQName: "w:val",
      observedValue: "true",
    };
  });
}

describe("completed-byte Office QA readback", () => {
  it("accepts QA-only ordinary-placeholder run normalization while strict v2 remains separate", async () => {
    const ordinary = await ordinaryPlaceholderFixture();
    expect(() =>
      readbackTemplateDocxOutput({
        source: ordinary.source,
        output: ordinary.officeSaved,
        ir: ordinary.ir,
        resolutions: ordinary.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: "ROUNDTRIP_FIELD_MISMATCH" }),
    );

    const result = verifyOfficeRoundTripQa(
      validInput(ordinary.officeSaved, undefined, ordinary),
    );
    expect(result.status).toBe("passed");
    expect(result.fields).toEqual([
      expect.objectContaining({
        status: "survived",
        controlKindMatches: true,
        valueMatches: true,
        controlStateMatches: true,
        occurrenceMatches: true,
        logicalBindingIdentityMatches: true,
        pathNormalizationObserved: false,
        serializationNormalized: true,
      }),
    ]);
  });

  it.each([
    ["unresolved blank", null],
    ["maximum approved length", "x".repeat(32_767)],
  ] as const)(
    "round-trips a tab-only table cell at %s",
    async (_name, value) => {
      const tabOnly = await tabOnlyTableCellFixture(value);

      expect(
        verifyOfficeRoundTripQa(
          validInput(tabOnly.officeSaved, undefined, tabOnly),
        ).status,
      ).toBe("passed");
    },
  );

  it("round-trips a tab-stop-only table cell without treating its paragraph property as clinical text", async () => {
    const tabOnly = await tabOnlyTableCellFixture();
    const actual = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: tabOnly.officeSaved,
      expected: tabOnly.expected,
    });

    expect(actual.fields).toHaveLength(1);
    expect(actual.unexpectedBindingCount).toBe(0);
    expect(actual.ambiguousBindingCount).toBe(0);
    expect(actual.fields[0]).toMatchObject({
      controlKind: "fixed_table_cell",
      actualOccurrences: 1,
      actualValueSha256: tabOnly.expected.fields[0]!.expectedValueSha256,
      outputObservedValueSha256:
        tabOnly.expected.fields[0]!.rendererObservedValueSha256,
    });
    expect(
      verifyOfficeRoundTripQa(
        validInput(tabOnly.officeSaved, undefined, tabOnly),
      ).status,
    ).toBe("passed");

    const encodedValue = TAB_ONLY_OFFICE_FIELD_VALUE.replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
    const changed = await mutateDocument(tabOnly.officeSaved, (xml) =>
      xml.replace(
        `<w:r><w:t>${encodedValue}</w:t></w:r>`,
        `<w:r><w:tab/><w:t>${encodedValue}</w:t></w:r>`,
      ),
    );
    expect(
      verifyOfficeRoundTripQa(validInput(changed, undefined, tabOnly))
        .blockerCodes,
    ).toContain("OFFICE_QA_FIELD_VALUE_CHANGED");
  });

  it("derives exact full-IR field values, control state, identity, and occurrences from bytes", () => {
    const actual = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: fixture.rendererOutput,
      expected: fixture.expected,
    });

    expect(actual.fields).toHaveLength(fixture.ir.fields.length);
    expect(actual.unexpectedBindingCount).toBe(0);
    expect(actual.ambiguousBindingCount).toBe(0);
    expect(actual.officeSavedDocxSha256).toBe(
      sha256OfficeDocxBytes(fixture.rendererOutput),
    );
    expect(actual.fields.map((field) => field.controlKind)).toEqual(
      expect.arrayContaining([
        "text_content_control",
        "dropdown_content_control",
        "combo_box_content_control",
        "date_content_control",
        "checkbox_content_control",
      ]),
    );
  });

  it("permits recorded path normalization only after byte-derived logical survival", async () => {
    const normalized = await mutateDocument(fixture.rendererOutput, (xml) =>
      xml.replace(
        '<w:sdt><w:sdtPr><w:id w:val="501"',
        '<w:proofErr w:type="spellStart"/><w:sdt><w:sdtPr><w:id w:val="501"',
      ),
    );
    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: normalized,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrow();

    const result = verifyOfficeRoundTripQa(validInput(normalized));
    expect(result.status).toBe("passed");
    expect(result.compatibilityEngineeringEligible).toBe(true);
    expect(result.fields.some((field) => field.pathNormalizationObserved)).toBe(
      true,
    );
    expect(result.readbackV2Boundary).toEqual({
      preOfficeRendererStatus: "passed",
      preOfficeRendererEvidenceSha256: preOfficeReadbackV2For().evidenceSha256,
      postOfficeSavedObservedStatus: "failed",
      qaResultDoesNotChangeProductionStatus: true,
    });
    expect(result.signingEligible).toBe(false);
    expect(result.mayAuthorizeSigning).toBe(false);
    expect(result.mayAuthorizeExportOrDownload).toBe(false);
    expect(result.officeCompatibilityApproved).toBe(false);
  });

  it("detects an altered checkbox from completed bytes rather than caller hashes", async () => {
    const changed = await mutateDocument(fixture.rendererOutput, (xml) =>
      xml
        .replace('w14:checked w14:val="1"', 'w14:checked w14:val="0"')
        .replace(">☒<", ">☐<"),
    );
    const result = verifyOfficeRoundTripQa(validInput(changed));
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toEqual(
      expect.arrayContaining([
        "OFFICE_QA_FIELD_VALUE_CHANGED",
        "OFFICE_QA_CONTROL_STATE_CHANGED",
      ]),
    );
  });

  it("does not null-coerce inserted assertions or changed unresolved checkbox bytes", async () => {
    const unresolvedLabels = new Set([
      "Synthetic narrative",
      "Synthetic reviewed",
      "Legacy synthetic check",
    ]);
    const resolutions = fixture.ir.fields.map((field) =>
      unresolvedLabels.has(field.originalLabel)
        ? FieldResolutionSchema.parse({
            fieldId: field.fieldId,
            status: "not_mentioned",
            value: null,
            sourceFactIds: [],
            evidenceAnchorIds: [],
            selectedOptionOrdinal: null,
            reasonCode: "synthetic_not_mentioned",
            clinicianReviewed: false,
          })
        : fixture.resolutions.find(
            (resolution) => resolution.fieldId === field.fieldId,
          )!,
    );
    const unresolvedFixture = await fixtureForResolutions(resolutions);

    const insertedAssertion = await mutateDocument(
      unresolvedFixture.rendererOutput,
      (xml) =>
        mutateSdtWithId(xml, "501", (control) =>
          control.replace(
            /<w:sdtContent>[\s\S]*?<\/w:sdtContent>/,
            "<w:sdtContent><w:r><w:t>Injected unsupported assertion</w:t></w:r></w:sdtContent>",
          ),
        ),
    );
    const assertionResult = verifyOfficeRoundTripQa(
      validInput(insertedAssertion, undefined, unresolvedFixture),
    );
    expect(assertionResult.blockerCodes).toContain(
      "OFFICE_QA_FIELD_VALUE_CHANGED",
    );
    expect(
      assertionResult.fields.find(
        (field) =>
          field.fieldId ===
          fixture.ir.fields.find(
            (candidate) => candidate.originalLabel === "Synthetic narrative",
          )?.fieldId,
      )?.observedByteValueMatches,
    ).toBe(false);

    const changedModernCheckbox = await mutateDocument(
      unresolvedFixture.rendererOutput,
      (xml) =>
        mutateSdtWithId(xml, "505", (control) =>
          control
            .replace('w14:checked w14:val="0"', 'w14:checked w14:val="1"')
            .replace(">☐<", ">☒<"),
        ),
    );
    expect(
      verifyOfficeRoundTripQa(
        validInput(changedModernCheckbox, undefined, unresolvedFixture),
      ).blockerCodes,
    ).toContain("OFFICE_QA_FIELD_VALUE_CHANGED");

    const changedLegacyCheckbox = await mutateDocument(
      unresolvedFixture.rendererOutput,
      (xml) =>
        mutateLegacyFieldWithName(xml, "Legacy synthetic check", (fieldXml) =>
          fieldXml
            .replace('<w:checked w:val="1"/>', '<w:checked w:val="0"/>')
            .replace(">☒<", ">☐<"),
        ),
    );
    expect(
      verifyOfficeRoundTripQa(
        validInput(changedLegacyCheckbox, undefined, unresolvedFixture),
      ).blockerCodes,
    ).toContain("OFFICE_QA_FIELD_VALUE_CHANGED");
  });

  it("implements Word on/off lexical and absent legacy-checkbox semantics exactly", async () => {
    for (const checkedElement of [
      "<w:checked/>",
      '<w:checked w:val="true"/>',
      '<w:checked w:val="on"/>',
    ]) {
      const variant = await mutateDocument(fixture.rendererOutput, (xml) =>
        mutateLegacyFieldWithName(xml, "Legacy synthetic check", (fieldXml) =>
          fieldXml.replace('<w:checked w:val="1"/>', checkedElement),
        ),
      );
      expect(verifyOfficeRoundTripQa(validInput(variant)).status).toBe(
        "passed",
      );
    }

    const explicitDefault = await mutateDocument(
      fixture.rendererOutput,
      (xml) =>
        mutateLegacyFieldWithName(xml, "Legacy synthetic check", (fieldXml) =>
          fieldXml
            .replace('<w:default w:val="0"/>', '<w:default w:val="1"/>')
            .replace('<w:checked w:val="1"/>', ""),
        ),
    );
    expect(verifyOfficeRoundTripQa(validInput(explicitDefault)).status).toBe(
      "passed",
    );

    const falseLexical = await mutateDocument(fixture.rendererOutput, (xml) =>
      mutateLegacyFieldWithName(xml, "Legacy synthetic check", (fieldXml) =>
        fieldXml
          .replace('<w:checked w:val="1"/>', '<w:checked w:val="off"/>')
          .replace(">☒<", ">☐<"),
      ),
    );
    const falseResult = verifyOfficeRoundTripQa(validInput(falseLexical));
    expect(falseResult.blockerCodes).toContain("OFFICE_QA_FIELD_VALUE_CHANGED");
    expect(falseResult.blockerCodes).not.toContain(
      "OFFICE_QA_EVIDENCE_INVALID",
    );

    for (const unsafeMutation of [
      (fieldXml: string) =>
        fieldXml
          .replace('<w:default w:val="0"/>', "")
          .replace('<w:checked w:val="1"/>', ""),
      (fieldXml: string) =>
        fieldXml.replace('<w:checked w:val="1"/>', '<w:checked w:val="yes"/>'),
      (fieldXml: string) =>
        fieldXml.replace(
          '<w:checked w:val="1"/>',
          '<w:checked w:val="1"/><w:checked w:val="0"/>',
        ),
    ]) {
      const unsafe = await mutateDocument(fixture.rendererOutput, (xml) =>
        mutateLegacyFieldWithName(
          xml,
          "Legacy synthetic check",
          unsafeMutation,
        ),
      );
      expect(
        verifyOfficeRoundTripQa(validInput(unsafe)).blockerCodes,
      ).toContain("OFFICE_QA_EVIDENCE_INVALID");
    }
  });

  it("accepts valid modern on/off normalizations and rejects invalid duplicates", async () => {
    for (const checkedAttribute of [
      "w14:checked",
      'w14:checked w14:val="true"',
      'w14:checked w14:val="on"',
    ]) {
      const normalized = await mutateDocument(fixture.rendererOutput, (xml) =>
        mutateSdtWithId(xml, "505", (control) =>
          control.replace('w14:checked w14:val="1"', checkedAttribute),
        ),
      );
      expect(verifyOfficeRoundTripQa(validInput(normalized)).status).toBe(
        "passed",
      );
    }

    const duplicate = await mutateDocument(fixture.rendererOutput, (xml) =>
      mutateSdtWithId(xml, "505", (control) =>
        control.replace(
          '<w14:checked w14:val="1"/>',
          '<w14:checked w14:val="1"/><w14:checked w14:val="0"/>',
        ),
      ),
    );
    expect(
      verifyOfficeRoundTripQa(validInput(duplicate)).blockerCodes,
    ).toContain("OFFICE_QA_EVIDENCE_INVALID");
  });

  it("hashes complete option lists and essential date/checkbox control metadata", async () => {
    const mutations = [
      (xml: string) =>
        mutateSdtWithId(xml, "502", (control) =>
          control.replace(
            'w:displayText="Alpha" w:value="alpha"',
            'w:displayText="Alpha" w:value="alpha_changed"',
          ),
        ),
      (xml: string) =>
        mutateLegacyFieldWithName(
          xml,
          "Legacy synthetic category",
          (fieldXml) =>
            fieldXml.replace(
              '<w:listEntry w:val="Alpha"/>',
              '<w:listEntry w:val="Altered Alpha"/>',
            ),
        ),
      (xml: string) =>
        mutateSdtWithId(xml, "504", (control) =>
          control.replace('w:val="yyyy-MM-dd"', 'w:val="MM/dd/yyyy"'),
        ),
      (xml: string) =>
        mutateSdtWithId(xml, "504", (control) =>
          control.replace('w:val="en-US"', 'w:val="en-GB"'),
        ),
      (xml: string) =>
        mutateSdtWithId(xml, "504", (control) =>
          control.replace('w:val="gregorian"', 'w:val="hijri"'),
        ),
      (xml: string) =>
        mutateSdtWithId(xml, "501", (control) =>
          control.replace("<w:text/>", '<w:text w:multiLine="true"/>'),
        ),
      (xml: string) =>
        mutateLegacyFieldWithName(xml, "Legacy synthetic note", (fieldXml) =>
          fieldXml.replace(
            'w:maxLength w:val="32767"',
            'w:maxLength w:val="1"',
          ),
        ),
      (xml: string) =>
        mutateLegacyFieldWithName(xml, "Legacy synthetic note", (fieldXml) =>
          fieldXml.replace('w:type w:val="regular"', 'w:type w:val="number"'),
        ),
      (xml: string) =>
        mutateSdtWithId(xml, "505", (control) =>
          control
            .replace(
              'w14:checkedState w14:val="2612"',
              'w14:checkedState w14:val="2611"',
            )
            .replace(">☒<", ">☑<"),
        ),
    ];
    for (const mutation of mutations) {
      const changed = await mutateDocument(fixture.rendererOutput, mutation);
      const result = verifyOfficeRoundTripQa(validInput(changed));
      expect(result.blockerCodes).toContain("OFFICE_QA_CONTROL_STATE_CHANGED");
    }
  });

  it("requires the visible legacy dropdown result, not metadata alone", async () => {
    const missingVisibleResult = await mutateDocument(
      fixture.rendererOutput,
      (xml) =>
        mutateLegacyFieldWithName(
          xml,
          "Legacy synthetic category",
          (fieldXml) => fieldXml.replace("<w:t>Beta</w:t>", "<w:t></w:t>"),
        ),
    );
    expect(
      verifyOfficeRoundTripQa(validInput(missingVisibleResult)).blockerCodes,
    ).toContain("OFFICE_QA_EVIDENCE_INVALID");
  });

  it("accepts only the exact LibreOffice calculated legacy dropdown with exact visual survival", async () => {
    const calculated = await mutateDocument(fixture.rendererOutput, (xml) =>
      mutateLegacyFieldWithName(xml, "Legacy synthetic category", (fieldXml) =>
        fieldXml.replace(
          "<w:r><w:t>Beta</w:t></w:r>",
          '<w:bookmarkStart w:id="910" w:name="Legacy_synthetic_category"/><w:bookmarkStart w:id="911" w:name="Legacy_synthetic_category"/><w:bookmarkEnd w:id="911"/><w:r></w:r>',
        ),
      ),
    );
    const result = verifyOfficeRoundTripQa(validInput(calculated));
    expect(result.status).toBe("passed");
    expect(
      result.fields.find(
        (field) =>
          field.fieldId ===
          fixture.ir.fields.find(
            (candidate) =>
              candidate.originalLabel === "Legacy synthetic category",
          )?.fieldId,
      ),
    ).toMatchObject({
      officeCalculatedPresentation: "libreoffice_legacy_dropdown",
      officeCalculatedPresentationVisuallyProven: true,
      valueMatches: true,
      controlStateMatches: true,
    });

    const nonidenticalInput = validInput(calculated);
    const page = nonidenticalInput.visualMetrics.pages[0]!;
    const { evidenceSha256: ignoredEvidenceSha256, ...visualWithoutHash } =
      nonidenticalInput.visualMetrics;
    expect(ignoredEvidenceSha256).toMatch(/^[a-f0-9]{64}$/);
    const nonidenticalVisualUnsigned = {
      ...visualWithoutHash,
      pages: [
        {
          ...page,
          differingPixels: 1,
          maximumChannelDifference: 1,
          approvedFieldRegionCount: 1,
          approvedFieldMaskSha256: sha("legacy-dropdown-field-mask"),
          differenceClassification: "field_region_only_reviewed" as const,
          humanReviewed: true,
        },
      ],
    };
    const nonidentical = verifyOfficeRoundTripQa({
      ...nonidenticalInput,
      visualMetrics: {
        ...nonidenticalVisualUnsigned,
        evidenceSha256: hashOfficePdfVisualMetricsEvidence(
          nonidenticalVisualUnsigned,
        ),
      },
    });
    expect(nonidentical.blockerCodes).toContain(
      "OFFICE_QA_FIELD_VALUE_CHANGED",
    );

    const duplicated = await mutateDocument(calculated, (xml) => {
      const marker = '<w:name w:val="Legacy synthetic category"';
      const markerOffset = xml.indexOf(marker);
      const start = xml.lastIndexOf("<w:p>", markerOffset);
      const end = xml.indexOf("</w:p>", markerOffset) + "</w:p>".length;
      if (markerOffset < 0 || start < 0 || end < "</w:p>".length) {
        throw new Error("Synthetic calculated legacy field missing.");
      }
      return xml.replace("</w:body>", `${xml.slice(start, end)}</w:body>`);
    });
    const duplicateResult = verifyOfficeRoundTripQa(validInput(duplicated));
    expect(duplicateResult.status).toBe("failed");
    expect(duplicateResult.blockerCodes).toEqual(
      expect.arrayContaining([
        "OFFICE_QA_FIELD_MISSING",
        "OFFICE_QA_UNEXPECTED_FIELD",
      ]),
    );
  });

  it("detects duplicated bindings and refuses incomplete actual coverage", async () => {
    const duplicated = await mutateDocument(fixture.rendererOutput, (xml) => {
      const start = xml.indexOf('<w:sdt><w:sdtPr><w:id w:val="501"');
      const end = xml.indexOf("</w:sdt>", start) + "</w:sdt>".length;
      if (start < 0 || end < 0) throw new Error("Synthetic SDT missing.");
      return xml.replace("</w:body>", `${xml.slice(start, end)}</w:body>`);
    });
    const result = verifyOfficeRoundTripQa(validInput(duplicated));
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toEqual(
      expect.arrayContaining([
        "OFFICE_QA_EVIDENCE_INVALID",
        "OFFICE_QA_UNEXPECTED_FIELD",
        "OFFICE_QA_FIELD_MISSING",
      ]),
    );
  });

  it("derives visible static evidence from bytes and rejects changed labels", async () => {
    const changed = await mutateDocument(fixture.rendererOutput, (xml) =>
      xml.replace("Synthetic narrative: ", "Changed static narrative: "),
    );
    const result = verifyOfficeRoundTripQa(validInput(changed));
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toContain("OFFICE_QA_VISIBLE_STATIC_CHANGED");
    expect(result.rendererVisibleStaticEvidenceSha256).toMatch(
      /^[a-f0-9]{64}$/,
    );
    expect(result.officeSavedVisibleStaticEvidenceSha256).toMatch(
      /^[a-f0-9]{64}$/,
    );
  });

  it("detects static visibility, font, color, highlight, and size mutations", async () => {
    const formattingProperties = [
      "<w:vanish/>",
      "<w:webHidden/>",
      "<w:specVanish/>",
      '<w:rFonts w:ascii="SyntheticAlteredFont"/>',
      '<w:color w:val="FFFFFF"/>',
      '<w:highlight w:val="black"/>',
      '<w:sz w:val="2"/>',
    ];
    for (const property of formattingProperties) {
      const changed = await mutateDocument(fixture.rendererOutput, (xml) =>
        xml.replace(
          "<w:r><w:t>Synthetic narrative: </w:t></w:r>",
          `<w:r><w:rPr>${property}</w:rPr><w:t>Synthetic narrative: </w:t></w:r>`,
        ),
      );
      const result = verifyOfficeRoundTripQa(validInput(changed));
      expect(result.status).toBe("failed");
      expect(result.blockerCodes).toContain(
        "OFFICE_QA_STATIC_STRUCTURE_CHANGED",
      );
    }

    for (const [index, normalization] of [
      (control: string) =>
        control.replace('<w:calendar w:val="gregorian"/>', ""),
      (control: string) =>
        control.replace('<w:storeMappedDataAs w:val="dateTime"/>', ""),
      (control: string) => control.replace('w:val="dateTime"', 'w:val="date"'),
    ].entries()) {
      const normalized = await mutateDocument(fixture.rendererOutput, (xml) =>
        mutateSdtWithId(xml, "504", normalization),
      );
      const normalizedResult = verifyOfficeRoundTripQa(validInput(normalized));
      expect(normalizedResult.status).toBe("passed");
      const dateField = normalizedResult.fields.find(
        (field) =>
          field.fieldId ===
          fixture.ir.fields.find(
            (candidate) => candidate.originalLabel === "Synthetic date",
          )?.fieldId,
      );
      expect(dateField?.behaviorNormalizations).toContain(
        "store_mapped_data_as_not_applicable_unbound",
      );
      if (index === 0) {
        expect(dateField?.behaviorNormalizations).toContain(
          "calendar_omitted_defaults_gregorian",
        );
      }
    }

    const bound = await mutateDocument(fixture.rendererOutput, (xml) =>
      mutateSdtWithId(xml, "504", (control) =>
        control.replace(
          "</w:sdtPr>",
          '<w:dataBinding w:xpath="/synthetic/date" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:sdtPr>',
        ),
      ),
    );
    expect(verifyOfficeRoundTripQa(validInput(bound)).blockerCodes).toContain(
      "OFFICE_QA_EVIDENCE_INVALID",
    );
  });

  it("rejects a recomputed expected manifest that omits an IR field", () => {
    const { manifestSha256: originalManifestSha256, ...unsigned } =
      fixture.expected;
    expect(originalManifestSha256).toMatch(/^[a-f0-9]{64}$/);
    const fields = unsigned.fields.slice(1);
    const tamperedUnsigned = {
      ...unsigned,
      fields,
      expectedIrFieldCount: fields.length,
      irFieldIdsSha256: canonicalSha256(
        fields.map((field) => field.fieldId).sort(),
      ),
    };
    const tampered = {
      ...tamperedUnsigned,
      manifestSha256: canonicalSha256(tamperedUnsigned),
    } as OfficeExpectedValueManifest;
    const result = verifyOfficeRoundTripQa({
      ...validInput(),
      expectedValues: tampered,
    });
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toContain("OFFICE_QA_EVIDENCE_INVALID");
  });

  it("rejects source bytes that do not match the certified IR", () => {
    expect(() =>
      buildOfficeExpectedValueManifest({
        syntheticOnly: true,
        sourceDocxBytes: fixture.rendererOutput,
        rendererOutputDocxBytes: fixture.rendererOutput,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrow("source bytes do not match");
  });
});

describe("schema, security, static, and visual provenance gates", () => {
  it("requires pinned, cross-bound Office execution evidence and pre-Office strict v2", () => {
    const input = validInput();
    expect(verifyOfficeRoundTripQa(input).status).toBe("passed");

    const missingExecution = verifyOfficeRoundTripQa({
      ...input,
      officeExecutionEvidence: undefined,
    } as unknown as VerifyOfficeRoundTripQaInput);
    expect(missingExecution.blockerCodes).toContain(
      "OFFICE_QA_OFFICE_EXECUTION_FAILED",
    );

    const { evidenceSha256: ignoredExecutionHash, ...executionUnsigned } =
      input.officeExecutionEvidence;
    expect(ignoredExecutionHash).toMatch(/^[a-f0-9]{64}$/);
    const wrongImageUnsigned = {
      ...executionUnsigned,
      imageDigest: `sha256:${"1".repeat(64)}`,
    };
    const wrongImage = {
      ...wrongImageUnsigned,
      evidenceSha256: canonicalSha256(wrongImageUnsigned),
    } as unknown as OfficeExecutionEvidence;
    expect(
      verifyOfficeRoundTripQa({
        ...input,
        officeExecutionEvidence: wrongImage,
      }).blockerCodes,
    ).toContain("OFFICE_QA_OFFICE_EXECUTION_FAILED");

    const zeroLogUnsigned = {
      ...executionUnsigned,
      commands: executionUnsigned.commands.map((command) => ({
        ...command,
        commandSha256: "0".repeat(64),
      })),
    };
    const zeroLog = {
      ...zeroLogUnsigned,
      evidenceSha256: canonicalSha256(zeroLogUnsigned),
    } as unknown as OfficeExecutionEvidence;
    expect(
      verifyOfficeRoundTripQa({
        ...input,
        officeExecutionEvidence: zeroLog,
      }).blockerCodes,
    ).toContain("OFFICE_QA_OFFICE_EXECUTION_FAILED");

    expect(
      verifyOfficeRoundTripQa(validInput(fixture.rendererOutput)).blockerCodes,
    ).toContain("OFFICE_QA_OFFICE_EXECUTION_FAILED");

    const { evidenceSha256: ignoredV2Hash, ...preV2Unsigned } =
      input.preOfficeRendererReadbackV2Evidence;
    expect(ignoredV2Hash).toMatch(/^[a-f0-9]{64}$/);
    const failedPreV2Unsigned = { ...preV2Unsigned, status: "failed" };
    const failedPreV2 = {
      ...failedPreV2Unsigned,
      evidenceSha256: canonicalSha256(failedPreV2Unsigned),
    } as unknown as VerifyOfficeRoundTripQaInput["preOfficeRendererReadbackV2Evidence"];
    expect(
      verifyOfficeRoundTripQa({
        ...input,
        preOfficeRendererReadbackV2Evidence: failedPreV2,
      }).blockerCodes,
    ).toContain("OFFICE_QA_PRE_OFFICE_READBACK_FAILED");
  });

  it("retains all 42 exact reviewed LibreOffice errors per target as external/Word-pending only", () => {
    const schema = schemaFor(
      fixture.officeSaved,
      classifiedExternalDiagnostics(),
    );
    expect(schema.status).toBe("external_tool_pending_word");
    expect(schema.compatibilityEngineeringEligible).toBe(true);
    expect(schema.stages).toHaveLength(6);
    expect(schema.matrix).toHaveLength(84);
    expect(new Set(schema.matrix.map((row) => row.targetFormat))).toEqual(
      new Set(["Office2013", "Microsoft365"]),
    );
    expect(
      schema.matrix.every(
        (row) =>
          row.requiresDesktopWordResolution &&
          !row.blocksQaGate &&
          row.severity === "error",
      ),
    ).toBe(true);

    const result = verifyOfficeRoundTripQa(
      validInput(fixture.officeSaved, schema),
    );
    expect(result.status).toBe("external_tool_pending_word");
    expect(result.gates.schema.status).toBe("external_tool_pending_word");
    expect(result.desktopWordApprovalStatus).toBe("pending");
    expect(result.signingEligible).toBe(false);
  });

  it("classifies only the exact pinned LibreOffice docGrid Int32 wrap as Word-pending", () => {
    const diagnostic: OfficeSchemaDiagnosticEvidence = {
      diagnosticId: "diagnostic-docgrid",
      validatorErrorId: "Sch_AttributeValueDataTypeDetailed",
      severity: "error",
      familyCode: "LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW",
      disposition: "external_tool_pending_word",
      descriptionSha256: sha("docgrid-description"),
      classificationRationaleSha256: sha("docgrid-rationale"),
      partName: "/word/document.xml",
      pathSha256: sha("docgrid-path"),
      elementQName: "w:docGrid",
      attributeQName: "w:charSpace",
      observedValue: "4294963199",
    };
    const schema = schemaFor(fixture.officeSaved, [diagnostic]);
    expect(schema).toMatchObject({
      status: "external_tool_pending_word",
      compatibilityEngineeringEligible: true,
      matrix: [
        {
          blocksQaGate: false,
          requiresDesktopWordResolution: true,
        },
        {
          blocksQaGate: false,
          requiresDesktopWordResolution: true,
        },
      ],
    });

    const changedValue = schemaFor(fixture.officeSaved, [
      { ...diagnostic, observedValue: "4294963198" },
    ]);
    expect(changedValue.status).toBe("failed");
    expect(changedValue.compatibilityEngineeringEligible).toBe(false);
  });

  it("rejects unknown error values, validator versions, targets, and source-stage downgrades", () => {
    const unknown = {
      ...classifiedExternalDiagnostics(1)[0]!,
      observedValue: "iso-8859-1",
    };
    const input = schemaInput(fixture.rendererOutput);
    const unknownResult = evaluateOfficeSchemaEvidence({
      ...input,
      stages: input.stages.map((stage) =>
        stage.stage === "office_saved" && stage.targetFormat === "Office2013"
          ? schemaStage(
              "office_saved",
              "office-saved.docx",
              fixture.expected.rendererOutputDocxSha256,
              [unknown],
              "Office2013",
            )
          : stage,
      ),
    });
    expect(unknownResult.status).toBe("failed");
    expect(unknownResult.blockerCodes).toContain(
      "OFFICE_SCHEMA_EXTERNAL_CLASSIFICATION_NOT_REVIEWED",
    );
    const wrongVersion = evaluateOfficeSchemaEvidence({
      ...input,
      stages: input.stages.map((stage) =>
        stage.stage === "office_saved" && stage.targetFormat === "Office2013"
          ? { ...stage, validatorVersion: "3.6.0" }
          : stage,
      ),
    });
    expect(wrongVersion.status).toBe("failed");

    const unknownTarget = evaluateOfficeSchemaEvidence({
      ...input,
      stages: input.stages.map((stage) =>
        stage.stage === "office_saved" && stage.targetFormat === "Microsoft365"
          ? { ...stage, targetFormat: "Office2024" }
          : stage,
      ),
    });
    expect(unknownTarget.status).toBe("failed");
    expect(unknownTarget.blockerCodes).toContain(
      "OFFICE_SCHEMA_STAGE_SET_INVALID",
    );

    const sourceDowngrade = evaluateOfficeSchemaEvidence({
      ...input,
      stages: input.stages.map((stage) =>
        stage.stage === "source" && stage.targetFormat === "Office2013"
          ? schemaStage(
              "source",
              "source.docx",
              fixture.expected.sourceDocxSha256,
              [classifiedExternalDiagnostics(1)[0]!],
              "Office2013",
            )
          : stage,
      ),
    });
    expect(sourceDowngrade.status).toBe("failed");
    expect(sourceDowngrade.blockerCodes).toContain(
      "OFFICE_SCHEMA_ERROR_PRESENT",
    );
  });

  it("rejects rehashed schema status, validator, duplicate-stage, and matrix forgeries", () => {
    const pending = schemaFor(
      fixture.officeSaved,
      classifiedExternalDiagnostics(),
    );
    const downgraded = rehashSchema(pending, (unsigned) => ({
      ...unsigned,
      status: "passed",
    }));
    expect(
      verifyOfficeRoundTripQa(validInput(fixture.officeSaved, downgraded))
        .blockerCodes,
    ).toContain("OFFICE_QA_SCHEMA_FAILED");

    const fakeValidator = rehashSchema(pending, (unsigned) => ({
      ...unsigned,
      stages: unsigned.stages.map((stage, index) =>
        index === 0 ? { ...stage, validatorVersion: "3.6.0" } : stage,
      ),
    }));
    expect(
      verifyOfficeRoundTripQa(validInput(fixture.officeSaved, fakeValidator))
        .blockerCodes,
    ).toContain("OFFICE_QA_SCHEMA_FAILED");

    const duplicateStage = rehashSchema(pending, (unsigned) => ({
      ...unsigned,
      stages: [...unsigned.stages, unsigned.stages[0]!],
    }));
    expect(
      verifyOfficeRoundTripQa(validInput(fixture.officeSaved, duplicateStage))
        .blockerCodes,
    ).toContain("OFFICE_QA_SCHEMA_FAILED");

    const matrix = pending.matrix.map((row, index) =>
      index === 0
        ? rehashSchemaMatrixRow(row, {
            blocksQaGate: true,
            requiresDesktopWordResolution: false,
            disposition: "blocking",
          })
        : row,
    );
    const forgedMatrix = rehashSchema(pending, (unsigned) => ({
      ...unsigned,
      matrix,
      matrixSha256: canonicalSha256(matrix),
    }));
    expect(
      verifyOfficeRoundTripQa(validInput(fixture.officeSaved, forgedMatrix))
        .blockerCodes,
    ).toContain("OFFICE_QA_SCHEMA_FAILED");
  });

  it("fails empty/incomplete schema stages instead of producing a vacuous pass", () => {
    const schema = evaluateOfficeSchemaEvidence({
      syntheticOnly: true,
      reviewerProvenance: reviewerProvenance(),
      requiredStages: [],
      stages: [],
    });
    expect(schema.status).toBe("failed");
    expect(schema.blockerCodes).toContain("OFFICE_SCHEMA_STAGE_SET_INVALID");

    const fabricated = schemaInput(fixture.officeSaved);
    const allZero = evaluateOfficeSchemaEvidence({
      ...fabricated,
      reviewerProvenance: {
        ...fabricated.reviewerProvenance,
        reviewRecordSha256: "0".repeat(64),
      },
      stages: fabricated.stages.map((stage) => ({
        ...stage,
        executionLogSha256: "0".repeat(64),
        artifacts: stage.artifacts.map((artifact) => ({
          ...artifact,
          validatorLogSha256: "0".repeat(64),
        })),
      })),
    });
    expect(allZero.status).toBe("failed");
    expect(allZero.compatibilityEngineeringEligible).toBe(false);
    expect(allZero.blockerCodes).toContain("OFFICE_SCHEMA_EVIDENCE_INVALID");
  });

  it("derives security from exact Office bytes and rejects a malicious relationship", async () => {
    const malicious = await mutatePackagePart(
      fixture.rendererOutput,
      "word/_rels/document.xml.rels",
      (xml) =>
        xml.replace(
          'Target="header1.xml"',
          'Target="https://synthetic.test/header.xml" TargetMode="External"',
        ),
    );
    const inspection = inspectOfficeDocxSecurityQa(malicious);
    expect(inspection.status).toBe("failed");
    expect(inspection.blockerCodes).toEqual(["PACKAGE_INSPECTION_REJECTED"]);
    const result = verifyOfficeRoundTripQa(validInput(malicious));
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toContain(
      "OFFICE_QA_SECURITY_INSPECTION_FAILED",
    );
  });

  it("rejects page gaps, invalid field masks, and unreviewed visual differences", () => {
    const input = validInput();
    const page = input.visualMetrics.pages[0]!;
    const unsigned = {
      ...input.visualMetrics,
      pages: [
        {
          ...page,
          pageNumber: 2,
          differingPixels: 10,
          approvedFieldRegionCount: 0,
          differenceClassification: "field_region_only_reviewed" as const,
          humanReviewed: false,
        },
      ],
      evidenceSha256: undefined,
    };
    const { evidenceSha256: originalVisualEvidenceSha256, ...withoutHash } =
      unsigned;
    expect(originalVisualEvidenceSha256).toBeUndefined();
    const visual = {
      ...withoutHash,
      evidenceSha256: hashOfficePdfVisualMetricsEvidence(withoutHash),
    } as OfficePdfVisualMetricsEvidence;
    const result = verifyOfficeRoundTripQa({ ...input, visualMetrics: visual });
    expect(result.status).toBe("failed");
    expect(result.blockerCodes).toContain("OFFICE_QA_EVIDENCE_INVALID");

    const { evidenceSha256: originalToolHash, ...visualWithoutHash } =
      input.visualMetrics;
    expect(originalToolHash).toMatch(/^[a-f0-9]{64}$/);
    const fakeToolUnsigned = {
      ...visualWithoutHash,
      rendererName: "NoOpImageComparator",
      rendererVersion: "0.0.0",
    };
    const fakeTool: OfficePdfVisualMetricsEvidence = {
      ...fakeToolUnsigned,
      evidenceSha256: hashOfficePdfVisualMetricsEvidence(fakeToolUnsigned),
    };
    expect(
      verifyOfficeRoundTripQa({ ...input, visualMetrics: fakeTool })
        .blockerCodes,
    ).toContain("OFFICE_QA_EVIDENCE_INVALID");
  });

  it("normalizes Unicode and whitespace without retaining raw static text", () => {
    expect(normalizeOfficeVisibleStaticText("  Cafe\u0301\r\n  label\t ")).toBe(
      "Café\nlabel",
    );
    const manifest = visibleStatic(fixture.expected.rendererOutputDocxSha256);
    expect(JSON.stringify(manifest)).not.toContain("Synthetic labels");
  });
});
