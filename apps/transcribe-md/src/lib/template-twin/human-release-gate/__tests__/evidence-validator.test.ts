import { createHash } from "node:crypto";

import JSZip from "jszip";
import PDFDocument from "pdfkit";
import { beforeAll, describe, expect, it } from "vitest";

import { buildSyntheticDocx } from "../../../note-template-docx/__tests__/synthetic-docx";
import { compileTemplateDocx } from "../../../note-template-docx/compiler";
import {
  buildOfficeExpectedValueManifest,
  buildOfficeVisibleStaticManifestFromDocxBytes,
  compareOfficeVisibleStaticManifests,
  type OfficeExpectedValueManifest,
} from "../../../note-template-docx/office-roundtrip-qa";
import { renderTemplateDocx } from "../../../note-template-docx/renderer";
import { canonicalSha256 } from "../../canonical";
import {
  PHYSICIAN_INTENT_DECISION_VERSION,
  PHYSICIAN_INTENT_MANIFEST_VERSION,
  createPhysicianIntentDecisionFile,
  type PhysicianIntentManifest,
} from "../../human-gate/physician-intent";
import {
  MEDIA_REVIEW_EVIDENCE_VERSION,
  createMediaReviewEvidenceFile,
} from "../../human-gate/media-review";
import { TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION } from "../../supported-concepts";
import {
  FieldResolutionSchema,
  type TemplateTwinValidationResult,
} from "../../ir";
import {
  WORD_DOCUMENT_MANIFEST_VERSION,
  WORD_HUMAN_EVIDENCE_VERSION,
  WORD_OPENXML_VALIDATOR_NAME,
  WORD_OPENXML_VALIDATOR_SDK_VERSION,
  WORD_VERIFICATION_CONTRACT_VERSION,
} from "../contracts";
import {
  validateReturnedHumanGateEvidence,
  type TrustedOpenXmlValidator,
} from "../evidence-validator";
import { verifyReturnedOfficeArtifacts } from "../../../../../scripts/template-twin-human-gate/returned-office-artifact-verifier";

const SOURCE_COMMIT = "a".repeat(40);
const OTHER_COMMIT = "b".repeat(40);
const CHECKED_AT = "2026-07-16T23:00:00.000Z";
const OPENXML_VALIDATOR_SHA256 = "c".repeat(64);
const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: CHECKED_AT,
  validatorVersion: "template-field-validator/1.0.0",
};

interface SyntheticOfficeFixture {
  readonly source: Buffer;
  readonly rendererOutput: Buffer;
  readonly staticTamperedRenderer: Buffer;
  readonly structureTamperedRenderer: Buffer;
  readonly layoutTamperedRenderers: Readonly<Record<string, Buffer>>;
  readonly expectedManifestBytes: Buffer;
  readonly sourcePdf: Buffer;
  readonly rendererPdf: Buffer;
}

let officeFixture: SyntheticOfficeFixture;

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function jsonBytes(value: unknown): Buffer {
  return Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function buildSyntheticPdf(text: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    const document = new PDFDocument({ autoFirstPage: true, compress: false });
    document.on("data", (chunk: Buffer) => chunks.push(chunk));
    document.on("error", reject);
    document.on("end", () => resolve(Buffer.concat(chunks)));
    document.text(text);
    document.end();
  });
}

beforeAll(async () => {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="left"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Synthetic finding: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="901"/><w:tag w:val="synthetic_finding"/><w:alias w:val="Synthetic finding"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter finding</w:t></w:r></w:sdtContent></w:sdt></w:p><w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid><w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr><w:p><w:r><w:t>Synthetic table</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="540" w:footer="540"/></w:sectPr></w:body></w:document>`;
  const source = await buildSyntheticDocx({
    documentXml,
    extraEntries: {
      "word/header1.xml": `<w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic header</w:t></w:r></w:p></w:hdr>`,
      "word/footer1.xml": `<w:ftr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic footer</w:t></w:r></w:p></w:ftr>`,
      "word/styles.xml": `<w:styles xmlns:w="${W}"><w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:basedOn w:val="Base"/><w:pPr><w:jc w:val="left"/><w:spacing w:after="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Base"><w:pPr><w:widowControl/></w:pPr></w:style></w:styles>`,
      "word/numbering.xml": `<w:numbering xmlns:w="${W}"><w:abstractNum w:abstractNumId="7"><w:nsid w:val="A1B2C3D4"/><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="7"/></w:num></w:numbering>`,
    },
  });
  const ir = compileTemplateDocx(source);
  if (ir.fields.length !== 1) throw new Error("Expected one synthetic field.");
  const resolutions = [
    FieldResolutionSchema.parse({
      fieldId: ir.fields[0]!.fieldId,
      status: "supported",
      value: "Synthetic stable finding",
      sourceFactIds: [`ttfact_${"a".repeat(24)}`],
      evidenceAnchorIds: ["synthetic-word-evidence-anchor"],
      selectedOptionOrdinal: null,
      reasonCode: "synthetic_word_evidence",
      clinicianReviewed: false,
    }),
  ];
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  const staticTamperedZip = await JSZip.loadAsync(rendered.document);
  const staticTamperedDocument = staticTamperedZip.file("word/document.xml");
  if (!staticTamperedDocument)
    throw new Error("Missing synthetic document XML.");
  staticTamperedZip.file(
    "word/document.xml",
    (await staticTamperedDocument.async("string")).replace(
      "Synthetic finding: ",
      "Altered static finding: ",
    ),
  );
  const structureTamperedZip = await JSZip.loadAsync(rendered.document);
  const structureTamperedDocument =
    structureTamperedZip.file("word/document.xml");
  if (!structureTamperedDocument)
    throw new Error("Missing synthetic document XML.");
  const structureXml = await structureTamperedDocument.async("string");
  const structureMutatedXml = structureXml.replace(
    "<w:r><w:t>Synthetic finding: </w:t></w:r>",
    '<w:r><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/></w:rPr><w:t>Synthetic finding: </w:t></w:r>',
  );
  if (structureMutatedXml === structureXml) {
    throw new Error("Synthetic font mutation did not apply.");
  }
  structureTamperedZip.file("word/document.xml", structureMutatedXml);
  const mutateRenderedEntry = async (
    partName: string,
    before: string,
    after: string,
  ): Promise<Buffer> => {
    const zip = await JSZip.loadAsync(rendered.document);
    const entry = zip.file(partName);
    if (!entry) throw new Error(`Missing synthetic layout part: ${partName}.`);
    const xml = await entry.async("string");
    const changed = xml.replace(before, after);
    if (changed === xml)
      throw new Error(`Synthetic layout mutation did not apply: ${partName}.`);
    zip.file(partName, changed);
    return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
  };
  const layoutTamperedRenderers = Object.fromEntries(
    await Promise.all(
      [
        [
          "paragraph-alignment",
          "word/document.xml",
          '<w:jc w:val="left"/>',
          '<w:jc w:val="center"/>',
        ],
        [
          "table-properties",
          "word/document.xml",
          '<w:tblLayout w:type="fixed"/>',
          '<w:tblLayout w:type="autofit"/>',
        ],
        [
          "row-properties",
          "word/document.xml",
          "<w:cantSplit/>",
          '<w:cantSplit w:val="false"/>',
        ],
        [
          "cell-properties",
          "word/document.xml",
          '<w:vAlign w:val="center"/>',
          '<w:vAlign w:val="bottom"/>',
        ],
        [
          "section-properties",
          "word/document.xml",
          '<w:pgMar w:top="1080"',
          '<w:pgMar w:top="1440"',
        ],
        [
          "normal-style",
          "word/styles.xml",
          '<w:jc w:val="left"/>',
          '<w:jc w:val="center"/>',
        ],
        [
          "numbering",
          "word/numbering.xml",
          '<w:lvlJc w:val="left"/>',
          '<w:lvlJc w:val="right"/>',
        ],
      ].map(async ([name, partName, before, after]) => [
        name!,
        await mutateRenderedEntry(partName!, before!, after!),
      ]),
    ),
  );
  const sourcePdf = await buildSyntheticPdf(
    "Synthetic finding: Enter finding Synthetic table Synthetic header Synthetic footer",
  );
  const rendererPdf = await buildSyntheticPdf(
    "Synthetic finding: Synthetic stable finding Synthetic table Synthetic header Synthetic footer",
  );
  officeFixture = {
    source,
    rendererOutput: rendered.document,
    staticTamperedRenderer: await staticTamperedZip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    }),
    structureTamperedRenderer: await structureTamperedZip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    }),
    layoutTamperedRenderers,
    expectedManifestBytes: jsonBytes(
      buildOfficeExpectedValueManifest({
        syntheticOnly: true,
        sourceDocxBytes: source,
        rendererOutputDocxBytes: rendered.document,
        ir,
        resolutions,
      }),
    ),
    sourcePdf,
    rendererPdf,
  };
});

function physicianManifest(commit = SOURCE_COMMIT): PhysicianIntentManifest {
  const fields = Array.from({ length: 7 }, (_, index) => {
    const number = index + 1;
    return {
      fieldId: `ttf_${number.toString(16).padStart(24, "0")}`,
      referenceNumber: `P-0${number}`,
      documentSection: "document_body" as const,
      location: {
        partName: "word/document.xml",
        tableIndex: 0,
        rowIndex: number,
        cellIndex: 1,
        paragraphOrdinal: number,
        certifiedPathSha256: number.toString(16).padStart(64, "1"),
      },
      safeVisibleContext: `P-0${number}: source text withheld; use authenticated preview.`,
      sourceTextDisclosure: "withheld_from_offline_packet" as const,
      placeholderSyntax: "angle" as const,
      detectedStructuralType: "ORDINARY_PLACEHOLDER_TOKEN_V1" as const,
      tokenTextSha256: number.toString(16).padStart(64, "2"),
      certifiedBindingSha256: number.toString(16).padStart(64, "3"),
      bindingOrdinal: number,
      sourceControlFingerprintSha256: number.toString(16).padStart(64, "4"),
      availableExistingClinicalConcepts: [
        { concept: "chief_complaint", physicianLabel: "Chief concern" },
      ],
      permittedIntentChoices: [
        "supported_concept",
        "custom_scalar_concept",
        "intentionally_static",
        "unresolved",
      ] as const,
      unansweredDecision: {
        intent: null,
        requiredness: null,
        dataType: null,
        units: [] as never[],
        allowedValues: [] as never[],
        polarityAndDenial: null,
        temporality: [] as never[],
        laterality: [] as never[],
        blankUnknownPolicy: null,
        maximumLengthOrRange: null,
        positiveSyntheticExample: null,
        negativeSyntheticExample: null,
        ambiguitySyntheticExample: null,
      },
      signingConsequence:
        "Unresolved, contradictory, or insufficiently tested clinical intent blocks formal certification and signing." as const,
    };
  });
  const content = {
    contractVersion: PHYSICIAN_INTENT_MANIFEST_VERSION,
    sourceCommit: commit,
    sourceDocumentSha256: "5".repeat(64),
    compilerVersion: "synthetic-compiler/1.0.0",
    irSchemaVersion: 1,
    generatedAtIso: CHECKED_AT,
    purpose: "offline_physician_review_worksheet_only" as const,
    certificationEffect:
      "none_authenticated_quillmd_certification_required" as const,
    safetyNotice:
      "Only a licensed physician may define clinical intent. This worksheet cannot activate a template or authorize signing." as const,
    conceptRegistryVersion: TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION,
    fields,
  };
  return {
    ...content,
    manifestSha256: canonicalSha256(content),
  } as PhysicianIntentManifest;
}

function physicianDecision(
  manifest: PhysicianIntentManifest,
  options: { unresolved?: boolean; role?: string } = {},
): unknown {
  const decision = createPhysicianIntentDecisionFile({
    contractVersion: PHYSICIAN_INTENT_DECISION_VERSION,
    sourceCommit: manifest.sourceCommit,
    sourceDocumentSha256: manifest.sourceDocumentSha256,
    manifestSha256: manifest.manifestSha256,
    reviewer: {
      name: "Synthetic Physician Reviewer",
      professionalRole: "licensed_physician",
      jurisdiction: "Synthetic Test Jurisdiction",
      licenseOrRegistrationReference: "SYNTHETIC-TEST-ONLY",
    },
    reviewedAtIso: CHECKED_AT,
    attestation: {
      IAmTheLicensedPhysicianNamedAbove: true,
      IUsedSyntheticExamplesOnly: true,
      IReviewedEveryPlaceholderWithoutDelegatingClinicalJudgment: true,
      IUnderstandThisWorksheetDoesNotCertifyOrActivateTheTemplate: true,
      IUnderstandFormalAuthenticatedReviewIsStillRequired: true,
    },
    decisions: manifest.fields.map((field, index) => ({
      fieldId: field.fieldId,
      referenceNumber: field.referenceNumber,
      intent:
        options.unresolved && index === 0
          ? ("unresolved" as const)
          : ("intentionally_static" as const),
      reason:
        options.unresolved && index === 0
          ? "A licensed physician has not yet resolved this synthetic field."
          : "A licensed physician marked this synthetic worksheet field as static.",
      signingConsequenceAcknowledged: true as const,
    })),
  });
  if (options.role === undefined) return decision;
  const altered = structuredClone(decision) as unknown as {
    payload: { reviewer: { professionalRole: string } };
    payloadSha256: string;
  };
  altered.payload.reviewer.professionalRole = options.role;
  altered.payloadSha256 = canonicalSha256(altered.payload);
  return altered;
}

function mediaEvidence(
  commit = SOURCE_COMMIT,
  options: { state?: "approved" | "pending_review"; role?: string } = {},
): unknown {
  const approved = options.state !== "pending_review";
  const evidence = createMediaReviewEvidenceFile({
    contractVersion: MEDIA_REVIEW_EVIDENCE_VERSION,
    sourceCommit: commit,
    authorizationEffect: "none_authenticated_quillmd_workflow_required",
    reviewer: {
      name: "Synthetic Practice Administrator",
      professionalRole: "authorized_practice_administrator",
      practiceId: "synthetic-practice",
      jurisdiction: "Synthetic Test Jurisdiction",
    },
    reviewedAtIso: CHECKED_AT,
    assetMetadata: {
      practiceScopedSha256: "6".repeat(64),
      mimeType: "image/png",
      width: 640,
      height: 160,
      byteCount: 2_048,
      scannerVersion: "synthetic-scanner/1.0.0",
      ocrEngineVersion: "synthetic-ocr/1.0.0",
      ocrEvidenceSha256: "7".repeat(64),
      metadataEvidenceSha256: "8".repeat(64),
      privacyEvidenceSha256: "9".repeat(64),
      privacyScanResult: "clear",
    },
    retentionAndVersion: {
      currentAuthenticatedState: approved ? "approved" : "pending_review",
      decisionVersion: 1,
      retentionPolicyStatus: approved ? "confirmed" : "policy_review_required",
      retentionPolicyReference: approved ? "synthetic-policy-reference" : null,
    },
    checklist: {
      reusablePracticeLogoOrStaticAsset: true,
      containsPatientInformation: false,
      containsPatientOrPersonNamesOrIdentifiers: false,
      containsAuthorizedOrganizationOrPracticeName: true,
      containsPersonPhotographs: false,
      containsBarcodesOrMachineReadableIdentifiers: false,
      containsHiddenOrUnreviewedMetadata: false,
      organizationOwnsOrMayUseAsset: true,
    },
    recommendation: approved
      ? "recommend_authenticated_approval"
      : "defer_for_privacy_review",
    reason: approved
      ? "Synthetic evidence was reviewed through the authenticated test workflow."
      : "Synthetic evidence remains pending authenticated privacy review.",
    attestation: {
      IAmAuthorizedForThisPractice: true,
      IReviewedOnlyThroughTheApprovedLocalOrAuthenticatedWorkflow: true,
      IDidNotUploadTheAssetToGitHubOrCI: true,
      IUnderstandFounderApprovalIsNotClinicalOrPrivacyApproval: true,
      IUnderstandApprovalIsPracticeScoped: true,
      IUnderstandAnyByteChangeRequiresNewApproval: true,
      IConfirmedRetentionAndVersionStatusFromAuthenticatedWorkflow: true,
      IUnderstandRevocationBlocksNewCertificationButDoesNotAlterSignedDocuments: true,
      IUnderstandThisWorksheetCannotApproveTheAsset: true,
    },
  });
  if (options.role === undefined) return evidence;
  const altered = structuredClone(evidence) as unknown as {
    payload: { reviewer: { professionalRole: string } };
    payloadSha256: string;
  };
  altered.payload.reviewer.professionalRole = options.role;
  altered.payloadSha256 = canonicalSha256(altered.payload);
  return altered;
}

interface MutableWordEvidence {
  readonly documents: Array<{
    allowlistedRelativePath: string;
    saveAsCompleted: boolean;
    generatedFiles: Array<{
      relativePath: string;
      sizeBytes: number;
      sha256: string;
      kind: string;
    }>;
  }>;
  readonly attestation: {
    reviewedOnlySyntheticDocuments: boolean;
    observedRepairDialogsInDesktopWord: boolean;
    completedVisualChecklistForEveryDocument: boolean;
    understandsAutomationCannotJudgeVisualCorrectness: boolean;
  };
}

interface WordPackageOptions {
  readonly commit?: string;
  readonly validatorSha256?: string;
  readonly mutateEvidence?: (evidence: MutableWordEvidence) => void;
  readonly mutateEntries?: (entries: Map<string, Buffer>) => void;
}

async function wordEvidenceZip(
  options: WordPackageOptions = {},
): Promise<Buffer> {
  const commit = options.commit ?? SOURCE_COMMIT;
  const validatorSha256 = options.validatorSha256 ?? OPENXML_VALIDATOR_SHA256;
  const expectedManifestRelativePath =
    "evidence/corpus/synthetic-office/office-expected-manifest.json";
  const originals = [
    {
      caseId: "synthetic-office",
      documentRole: "source" as const,
      relativePath: "documents/synthetic-office/synthetic-office.source.docx",
      bytes: officeFixture.source,
    },
    {
      caseId: "synthetic-office",
      documentRole: "renderer_output" as const,
      relativePath:
        "documents/synthetic-office/synthetic-office.renderer-output.docx",
      bytes: officeFixture.rendererOutput,
    },
  ];
  const manifest = {
    contractVersion: WORD_DOCUMENT_MANIFEST_VERSION,
    sourceCommit: commit,
    artifactName: `template-twin-human-gate-${commit.slice(0, 12)}`,
    syntheticOnly: true,
    generatedAtIso: CHECKED_AT,
    originalsMayBeOpenedByWord: false,
    openXmlValidator: {
      name: WORD_OPENXML_VALIDATOR_NAME,
      sdkVersion: WORD_OPENXML_VALIDATOR_SDK_VERSION,
      executableSha256: validatorSha256,
      targets: ["Office2013", "Microsoft365"],
    },
    documentCount: originals.length,
    documents: originals.map((document) => ({
      caseId: document.caseId,
      documentRole: document.documentRole,
      relativePath: document.relativePath,
      sizeBytes: document.bytes.length,
      sha256: sha256(document.bytes),
      expectedPageCount: 1,
      minimumExpectedPages: 1,
      verification: {
        contractVersion: WORD_VERIFICATION_CONTRACT_VERSION,
        expectedValueManifest: {
          relativePath: expectedManifestRelativePath,
          sizeBytes: officeFixture.expectedManifestBytes.length,
          sha256: sha256(officeFixture.expectedManifestBytes),
        },
      },
    })),
  };
  const manifestBytes = jsonBytes(manifest);
  const entries = new Map<string, Buffer>([
    [WORD_DOCUMENT_MANIFEST_PATH, manifestBytes],
    [expectedManifestRelativePath, officeFixture.expectedManifestBytes],
  ]);
  const documentEvidence = originals.map((document) => {
    const safeStem = `${document.caseId}--${document.documentRole}`;
    const reopened = document.bytes;
    const pdf =
      document.documentRole === "source"
        ? officeFixture.sourcePdf
        : officeFixture.rendererPdf;
    const pdfExportBinding = jsonBytes({
      contractVersion: "template-twin-word-pdf-export-binding/1.0.0",
      sourceCommit: commit,
      syntheticOnly: true,
      authorizesClinicalOrProductionAction: false,
      caseId: document.caseId,
      documentRole: document.documentRole,
      reopenedDocxSha256: sha256(reopened),
      reopenedDocxSizeBytes: reopened.length,
      exportedPdfSha256: sha256(pdf),
      exportedPdfSizeBytes: pdf.length,
      wordPageCount: 1,
      recordedAtIso: CHECKED_AT,
    });
    const openXmlReport = (target: "Office2013" | "Microsoft365") =>
      jsonBytes({
        tool: WORD_OPENXML_VALIDATOR_NAME,
        sdkVersion: WORD_OPENXML_VALIDATOR_SDK_VERSION,
        packageVersion: "3.5.1+synthetic.test",
        validatorExecutableSha256: validatorSha256,
        targetFileFormat: target,
        sourceCommit: commit,
        generatedAt: CHECKED_AT,
        results: [
          {
            file: `${safeStem}.word-reopened.docx`,
            sha256: sha256(reopened),
            sizeBytes: reopened.length,
            opened: true,
            valid: true,
            errorCount: 0,
            errors: [],
          },
        ],
      });
    const generated = [
      {
        relativePath: `work-copies/${safeStem}.work-copy.docx`,
        sizeBytes: document.bytes.length,
        sha256: sha256(document.bytes),
        kind: "work_copy",
        bytes: document.bytes,
      },
      {
        relativePath: `word-reopened-docx/${safeStem}.word-reopened.docx`,
        sizeBytes: reopened.length,
        sha256: sha256(reopened),
        kind: "word_reopened_docx",
        bytes: reopened,
      },
      {
        relativePath: `word-exported-pdf/${safeStem}.word.pdf`,
        sizeBytes: pdf.length,
        sha256: sha256(pdf),
        kind: "word_exported_pdf",
        bytes: pdf,
      },
      {
        relativePath: `pdf-export-binding/${safeStem}.pdf-export-binding.json`,
        sizeBytes: pdfExportBinding.length,
        sha256: sha256(pdfExportBinding),
        kind: "pdf_export_binding_json",
        bytes: pdfExportBinding,
      },
      {
        relativePath: `openxml/${safeStem}.Office2013.json`,
        sizeBytes: openXmlReport("Office2013").length,
        sha256: sha256(openXmlReport("Office2013")),
        kind: "openxml_office2013_json",
        bytes: openXmlReport("Office2013"),
      },
      {
        relativePath: `openxml/${safeStem}.Microsoft365.json`,
        sizeBytes: openXmlReport("Microsoft365").length,
        sha256: sha256(openXmlReport("Microsoft365")),
        kind: "openxml_microsoft365_json",
        bytes: openXmlReport("Microsoft365"),
      },
    ];
    for (const file of generated) entries.set(file.relativePath, file.bytes);
    return {
      caseId: document.caseId,
      documentRole: document.documentRole,
      allowlistedRelativePath: document.relativePath,
      originalExpectedSha256: sha256(document.bytes),
      originalExpectedSizeBytes: document.bytes.length,
      originalBeforeSha256: sha256(document.bytes),
      originalAfterSha256: sha256(document.bytes),
      originalUnchanged: true,
      automationStatus: "COMPLETED",
      automationErrorCode: "NONE",
      saveAsCompleted: true,
      reopenReadOnlyCompleted: true,
      pdfExportCompleted: true,
      pageCountBeforeSave: 1,
      pageCountAfterReopen: 1,
      expectedPageCount: 1,
      pageCountMatchesExpected: true,
      minimumExpectedPages: 1,
      compatibilityModeBeforeSave: 15,
      compatibilityModeAfterReopen: 15,
      generatedFiles: generated.map((file) => ({
        relativePath: file.relativePath,
        sizeBytes: file.sizeBytes,
        sha256: file.sha256,
        kind: file.kind,
      })),
      humanObservation: {
        repairDialog: "NO_REPAIR_DIALOG",
        visibleClinicalValues: "PASS",
        controlBehavior: "PASS",
        duplicateOrMissingFields: "PASS",
        clinicallyMeaningfulStaticText: "PASS",
        tablesHeadersAndFooters: "PASS",
        marginsFontsAndPagination: "PASS",
        overall: "PASS",
      },
    };
  });
  const evidence = {
    contractVersion: WORD_HUMAN_EVIDENCE_VERSION,
    sourceCommit: commit,
    packageManifestSha256: sha256(manifestBytes),
    syntheticOnly: true,
    reviewedAtIso: CHECKED_AT,
    reviewer: { reviewerId: "synthetic.qa", role: "desktop_word_qa_reviewer" },
    environment: {
      windowsVersion: "Synthetic Windows Test",
      wordVersion: "Synthetic Word Test",
      wordBuild: "Synthetic Build",
      wordProductCode: "Synthetic Product",
    },
    networkRequestsMadeByScript: 0,
    administratorPrivilegesRequired: false,
    originalsOpenedByWord: 0,
    documentsExpected: documentEvidence.length,
    documentsCompleted: documentEvidence.length,
    documentsFailedOrBlocked: 0,
    documents: documentEvidence,
    attestation: {
      reviewedOnlySyntheticDocuments: true,
      observedRepairDialogsInDesktopWord: true,
      completedVisualChecklistForEveryDocument: true,
      understandsAutomationCannotJudgeVisualCorrectness: true,
    },
  };
  options.mutateEvidence?.(evidence);
  entries.set(WORD_EVIDENCE_PATH, jsonBytes(evidence));
  options.mutateEntries?.(entries);
  const hashManifest = {
    contractVersion: "template-twin-return-evidence-file-hashes/1.0.0",
    files: [...entries.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([relativePath, bytes]) => ({
        relativePath,
        sizeBytes: bytes.length,
        sha256: sha256(bytes),
      })),
  };
  entries.set(FILE_HASH_MANIFEST_PATH, jsonBytes(hashManifest));
  const zip = new JSZip();
  for (const [name, bytes] of entries)
    zip.file(name, bytes, { createFolders: false });
  return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
}

const WORD_DOCUMENT_MANIFEST_PATH = "WORD-QA-DOCUMENTS.json";
const WORD_EVIDENCE_PATH = "WORD-EVIDENCE.json";
const FILE_HASH_MANIFEST_PATH = "RESULT-FILE-HASHES.json";

async function originalCiPackageZipFromReturnedEvidence(
  returnedEvidenceZip: Buffer,
): Promise<Buffer> {
  const returned = await JSZip.loadAsync(returnedEvidenceZip);
  const manifestFile = returned.file(WORD_DOCUMENT_MANIFEST_PATH);
  if (!manifestFile) throw new Error("Missing returned manifest fixture.");
  const manifestBytes = await manifestFile.async("nodebuffer");
  const original = new JSZip();
  original.file(`manifests/${WORD_DOCUMENT_MANIFEST_PATH}`, manifestBytes, {
    createFolders: false,
  });
  return original.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
  });
}

const trustedOpenXmlValidator: TrustedOpenXmlValidator = async (input) => ({
  contractVersion: "template-twin-trusted-openxml-rerun/1.0.0",
  tool: WORD_OPENXML_VALIDATOR_NAME,
  sdkVersion: WORD_OPENXML_VALIDATOR_SDK_VERSION,
  validatorSourceCommit: input.expectedSourceCommit,
  validatorExecutableSha256: "d".repeat(64),
  returnedExecutableUsed: false,
  networkModeDuringValidation: "none",
  targetFileFormat: input.targetFileFormat,
  documentFilename: input.documentFilename,
  documentSha256: sha256(input.documentBytes),
  documentSizeBytes: input.documentBytes.byteLength,
  valid: true,
  errorCount: 0,
});

async function validInputs(
  options: {
    word?: WordPackageOptions;
    unresolved?: boolean;
    physicianRole?: string;
    mediaState?: "approved" | "pending_review";
    mediaRole?: string;
  } = {},
) {
  const manifest = physicianManifest(options.word?.commit ?? SOURCE_COMMIT);
  const zip = await wordEvidenceZip(options.word);
  const originalCiPackageZip =
    await originalCiPackageZipFromReturnedEvidence(zip);
  return {
    expectedSourceCommit: SOURCE_COMMIT,
    originalCiPackageZip,
    expectedOriginalCiPackageZipSha256: sha256(originalCiPackageZip),
    wordEvidenceZip: zip,
    expectedWordEvidenceZipSha256: sha256(zip),
    physicianManifestJson: jsonBytes(manifest),
    physicianDecisionJson: jsonBytes(
      physicianDecision(manifest, {
        unresolved: options.unresolved,
        role: options.physicianRole,
      }),
    ),
    mediaReviewJson: jsonBytes(
      mediaEvidence(options.word?.commit ?? SOURCE_COMMIT, {
        state: options.mediaState,
        role: options.mediaRole,
      }),
    ),
    officeArtifactVerifier: verifyReturnedOfficeArtifacts,
    trustedOpenXmlValidator,
    checkedAtIso: CHECKED_AT,
  };
}

describe("returned Template Twin human-gate evidence validation", () => {
  it("passes complete, hash-bound synthetic Word, physician, and media evidence without authorizing action", async () => {
    const report = await validateReturnedHumanGateEvidence(await validInputs());

    expect(report.status, JSON.stringify(report.issues)).toBe("PASS");
    expect(report.issues).toEqual([]);
    expect(report.authorizesClinicalOrProductionAction).toBe(false);
    expect(report.sourceCommit).toBe(SOURCE_COMMIT);
  });

  it("rejects a self-consistent replacement ZIP that is not bound to the independently trusted original CI package", async () => {
    const trusted = await validInputs();
    const replacement = await validInputs({
      word: { validatorSha256: "e".repeat(64) },
    });
    const report = await validateReturnedHumanGateEvidence({
      ...replacement,
      originalCiPackageZip: trusted.originalCiPackageZip,
      expectedOriginalCiPackageZipSha256:
        trusted.expectedOriginalCiPackageZipSha256,
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_TRUSTED_MANIFEST_MISMATCH",
    );
  });

  it("fails closed when the out-of-band original CI package digest is absent", async () => {
    const inputs = await validInputs();
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      expectedOriginalCiPackageZipSha256: undefined,
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_ORIGINAL_CI_PACKAGE_HASH_MISSING",
    );
  });

  it("fails a valid reopened DOCX whose synthetic semantic value no longer matches", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "word-reopened-docx/synthetic-office--renderer_output.word-reopened.docx",
              officeFixture.source,
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_SEMANTIC_READBACK_MISMATCH",
    );
  });

  it("fails a reopened DOCX with changed normalized static content", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "word-reopened-docx/synthetic-office--renderer_output.word-reopened.docx",
              officeFixture.staticTamperedRenderer,
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_STATIC_OR_OCCURRENCE_MISMATCH",
    );
  });

  it("fails a font/layout structure mutation even when visible text is unchanged", async () => {
    const expected = JSON.parse(
      officeFixture.expectedManifestBytes.toString("utf8"),
    ) as OfficeExpectedValueManifest;
    const before = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: officeFixture.rendererOutput,
      expected,
    });
    const after = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: officeFixture.structureTamperedRenderer,
      expected,
    });
    expect(
      compareOfficeVisibleStaticManifests(before.manifest, after.manifest),
    ).toMatchObject({
      aggregateVisibleContentMatches: true,
      aggregateStructureMatches: false,
    });

    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "word-reopened-docx/synthetic-office--renderer_output.word-reopened.docx",
              officeFixture.structureTamperedRenderer,
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_STATIC_OR_OCCURRENCE_MISMATCH",
    );
  });

  it.each([
    "paragraph-alignment",
    "table-properties",
    "row-properties",
    "cell-properties",
    "section-properties",
    "normal-style",
    "numbering",
  ])(
    "fails canonical %s layout drift with unchanged clinical text",
    async (mutation) => {
      const tampered = officeFixture.layoutTamperedRenderers[mutation];
      if (!tampered)
        throw new Error(`Missing layout mutation fixture: ${mutation}.`);
      const report = await validateReturnedHumanGateEvidence(
        await validInputs({
          word: {
            mutateEntries(entries) {
              entries.set(
                "word-reopened-docx/synthetic-office--renderer_output.word-reopened.docx",
                tampered,
              );
            },
          },
        }),
      );

      expect(report.status).toBe("FAIL");
      expect(report.issues.map((issue) => issue.code)).toContain(
        "TT_HUMAN_GATE_WORD_LAYOUT_INTEGRITY_MISMATCH",
      );
    },
  );

  it("rejects a self-consistent stale same-page-count PDF substitution", async () => {
    const stalePdf = officeFixture.sourcePdf;
    const stalePath =
      "word-exported-pdf/synthetic-office--renderer_output.word.pdf";
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            const file = evidence.documents[1]!.generatedFiles.find(
              (candidate) => candidate.relativePath === stalePath,
            );
            if (!file)
              throw new Error("Missing renderer PDF fixture evidence.");
            file.sizeBytes = stalePdf.length;
            file.sha256 = sha256(stalePdf);
          },
          mutateEntries(entries) {
            entries.set(stalePath, stalePdf);
          },
        },
      }),
    );

    const codes = report.issues.map((issue) => issue.code);
    expect(report.status).toBe("FAIL");
    expect(codes).not.toContain("TT_HUMAN_GATE_WORD_GENERATED_FILE_MISMATCH");
    expect(codes).toContain("TT_HUMAN_GATE_WORD_PDF_SEMANTIC_LAYOUT_MISMATCH");
    expect(codes).toContain("TT_HUMAN_GATE_WORD_PDF_EXPORT_BINDING_MISMATCH");
  });

  it("rejects stale Open XML reports whose DOCX hash and size no longer match the returned bytes", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "word-reopened-docx/synthetic-office--renderer_output.word-reopened.docx",
              officeFixture.staticTamperedRenderer,
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_OPENXML_SCHEMA_INVALID",
    );
  });

  it("rejects a substituted Open XML report with the right filename but another DOCX identity", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            const reportPath =
              "openxml/synthetic-office--renderer_output.Office2013.json";
            const parsed = JSON.parse(
              entries.get(reportPath)!.toString("utf8"),
            ) as {
              results: Array<{ sha256: string; sizeBytes: number }>;
            };
            parsed.results[0]!.sha256 = sha256(officeFixture.source);
            parsed.results[0]!.sizeBytes = officeFixture.source.length;
            entries.set(reportPath, jsonBytes(parsed));
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_OPENXML_SCHEMA_INVALID",
    );
  });

  it("requires a fresh trusted Open XML rerun instead of accepting returned reports alone", async () => {
    const inputs = await validInputs();
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      trustedOpenXmlValidator: async (input) => ({
        ...(await trustedOpenXmlValidator(input)),
        valid: false,
        errorCount: 1,
      }),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_TRUSTED_OPENXML_RERUN_INVALID",
    );
  });

  it("fails fabricated or malformed post-Word Open XML evidence", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "openxml/synthetic-office--source.Office2013.json",
              jsonBytes({ valid: true }),
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_OPENXML_SCHEMA_INVALID",
    );
  });

  it("fails a generated artifact path that does not match its document identity", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            evidence.documents[0].generatedFiles[0]!.relativePath =
              "work-copies/substituted.work-copy.docx";
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_GENERATED_PATH_MISMATCH",
    );
  });

  it("fails when Word save/reopen/export completion is only implied", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            evidence.documents[0].saveAsCompleted = false;
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_SAVE_REOPEN_EXPORT_INCOMPLETE",
    );
  });

  it("fails incomplete Word document evidence", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            evidence.documents[0].generatedFiles =
              evidence.documents[0].generatedFiles.slice(0, 2);
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_GENERATED_EVIDENCE_INCOMPLETE",
    );
  });

  it("fails tampered evidence bytes even when the ZIP remains structurally valid", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEntries(entries) {
            entries.set(
              "word-exported-pdf/synthetic-office--source.word.pdf",
              Buffer.from("%PDF-1.7\nchanged synthetic.test evidence\n"),
            );
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_GENERATED_FILE_MISMATCH",
    );
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_EXPORTED_PDF_INVALID",
    );
  });

  it("rejects all evidence created for a stale Template Twin commit", async () => {
    const inputs = await validInputs({ word: { commit: OTHER_COMMIT } });
    const report = await validateReturnedHumanGateEvidence(inputs);

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_SOURCE_MISMATCH",
    );
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_PHYSICIAN_SOURCE_MISMATCH",
    );
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_MEDIA_SOURCE_MISMATCH",
    );
  });

  it("rejects founder-only clinical approval", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({ physicianRole: "founder" }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_PHYSICIAN_EVIDENCE_INVALID",
    );
  });

  it("rejects an incomplete set of physician decisions", async () => {
    const inputs = await validInputs();
    const incomplete = JSON.parse(
      inputs.physicianDecisionJson.toString("utf8"),
    ) as {
      payload: { decisions: unknown[] };
      payloadSha256: string;
    };
    incomplete.payload.decisions.pop();
    incomplete.payloadSha256 = canonicalSha256(incomplete.payload);
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      physicianDecisionJson: jsonBytes(incomplete),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_PHYSICIAN_EVIDENCE_INVALID",
    );
  });

  it("rejects a physician decision payload altered without a matching digest", async () => {
    const inputs = await validInputs();
    const altered = JSON.parse(
      inputs.physicianDecisionJson.toString("utf8"),
    ) as {
      payload: { decisions: Array<{ reason: string }> };
    };
    altered.payload.decisions[0].reason =
      "This synthetic decision was altered after the physician worksheet was exported.";
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      physicianDecisionJson: jsonBytes(altered),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_DECISION_HASH_MISMATCH",
    );
  });

  it("rejects media evidence from the wrong reviewer role", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({ mediaRole: "founder" }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_MEDIA_EVIDENCE_INVALID",
    );
  });

  it("fails Word evidence bound to a mismatched document path", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            evidence.documents[0].allowlistedRelativePath =
              "documents/substituted.docx";
          },
        },
      }),
    );

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_DOCUMENT_MISMATCH",
    );
  });

  it("blocks, rather than passes, an explicit unresolved physician decision", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({ unresolved: true }),
    );

    expect(report.status).toBe("BLOCKED");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_PHYSICIAN_UNRESOLVED",
    );
  });

  it("blocks unauthenticated or deferred media review", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({ mediaState: "pending_review" }),
    );

    expect(report.status).toBe("BLOCKED");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_MEDIA_REVIEW_INCOMPLETE",
    );
  });

  it("fails when the adjacent Word ZIP digest does not match", async () => {
    const inputs = await validInputs();
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      expectedWordEvidenceZipSha256: "0".repeat(64),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_ZIP_HASH_MISMATCH",
    );
  });

  it("fails when the required adjacent Word ZIP digest is absent", async () => {
    const inputs = await validInputs();
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      expectedWordEvidenceZipSha256: undefined,
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_ZIP_HASH_MISSING",
    );
  });

  it("blocks incomplete Word human-review attestations", async () => {
    const report = await validateReturnedHumanGateEvidence(
      await validInputs({
        word: {
          mutateEvidence(evidence) {
            evidence.attestation.completedVisualChecklistForEveryDocument = false;
          },
        },
      }),
    );

    expect(report.status).toBe("BLOCKED");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_ATTESTATION_INCOMPLETE",
    );
  });

  it("rejects changed ZIP evidence that no longer matches the internal file-hash manifest", async () => {
    const inputs = await validInputs();
    const zip = await JSZip.loadAsync(inputs.wordEvidenceZip);
    zip.file(
      "word-exported-pdf/synthetic-office--source.word.pdf",
      "%PDF-1.7\nchanged after internal manifest generation\n",
      { createFolders: false },
    );
    const altered = await zip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    });
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      wordEvidenceZip: altered,
      expectedWordEvidenceZipSha256: sha256(altered),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_WORD_FILE_HASH_MISMATCH",
    );
  });

  it("rejects a traversal entry before decompression", async () => {
    const inputs = await validInputs();
    const zip = await JSZip.loadAsync(inputs.wordEvidenceZip);
    zip.file("../escaped.txt", "synthetic.test traversal sentinel", {
      createFolders: false,
    });
    const unsafe = await zip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    });
    const report = await validateReturnedHumanGateEvidence({
      ...inputs,
      wordEvidenceZip: unsafe,
      expectedWordEvidenceZipSha256: sha256(unsafe),
    });

    expect(report.status).toBe("FAIL");
    expect(report.issues.map((issue) => issue.code)).toContain(
      "TT_HUMAN_GATE_ZIP_PATH_OR_DUPLICATE",
    );
  });
});
