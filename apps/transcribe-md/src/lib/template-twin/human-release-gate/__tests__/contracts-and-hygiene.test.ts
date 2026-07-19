import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import Ajv2020 from "ajv/dist/2020";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  buildSyntheticDocx,
  syntheticOpc,
} from "../../../note-template-docx/__tests__/synthetic-docx";
import {
  EVIDENCE_FILE_HASH_MANIFEST_JSON_SCHEMA,
  WORD_DOCUMENT_MANIFEST_JSON_SCHEMA,
  WORD_HUMAN_EVIDENCE_JSON_SCHEMA,
  WordHumanEvidenceSchema,
} from "../contracts";
import { scanHumanGateDirectory, sha256 } from "../artifact-hygiene";

const SHA = "a".repeat(40);
const DIGEST = "b".repeat(64);

function validWordEvidence(): Record<string, unknown> {
  const document = (caseId: string) => ({
    caseId,
    documentRole: "source",
    allowlistedRelativePath: `documents/${caseId}/${caseId}.source.docx`,
    originalExpectedSha256: DIGEST,
    originalExpectedSizeBytes: 100,
    originalBeforeSha256: DIGEST,
    originalAfterSha256: DIGEST,
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
    generatedFiles: [],
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
  });
  return {
    contractVersion: "template-twin-desktop-word-human-evidence/2.0.0",
    sourceCommit: SHA,
    packageManifestSha256: DIGEST,
    syntheticOnly: true,
    reviewedAtIso: "2026-07-16T00:00:00.000Z",
    reviewer: {
      reviewerId: "qa-reviewer-01",
      role: "desktop_word_qa_reviewer",
    },
    environment: {
      windowsVersion: "Synthetic Windows version",
      wordVersion: "16.0",
      wordBuild: "synthetic-build",
      wordProductCode: "synthetic-product",
    },
    networkRequestsMadeByScript: 0,
    administratorPrivilegesRequired: false,
    originalsOpenedByWord: 0,
    documentsExpected: 2,
    documentsCompleted: 2,
    documentsFailedOrBlocked: 0,
    documents: [document("case-one"), document("case-two")],
    attestation: {
      reviewedOnlySyntheticDocuments: true,
      observedRepairDialogsInDesktopWord: true,
      completedVisualChecklistForEveryDocument: true,
      understandsAutomationCannotJudgeVisualCorrectness: true,
    },
  };
}

describe("human release-gate contracts", () => {
  it("emits complete Draft 2020-12 schemas accepted by an independent validator", () => {
    const ajv = new Ajv2020({
      allErrors: true,
      strict: false,
      validateFormats: false,
    });
    for (const schema of [
      WORD_HUMAN_EVIDENCE_JSON_SCHEMA,
      WORD_DOCUMENT_MANIFEST_JSON_SCHEMA,
      EVIDENCE_FILE_HASH_MANIFEST_JSON_SCHEMA,
    ]) {
      expect(() => ajv.compile(schema)).not.toThrow();
      expect(schema).toHaveProperty("properties");
      expect(schema).toHaveProperty("additionalProperties", false);
    }
    const validate = ajv.compile(WORD_HUMAN_EVIDENCE_JSON_SCHEMA);
    const evidence = validWordEvidence();
    expect(WordHumanEvidenceSchema.parse(evidence)).toEqual(evidence);
    expect(validate(evidence), JSON.stringify(validate.errors)).toBe(true);
    expect(validate({ ...evidence, sourceCommit: "stale" })).toBe(false);
  });

  it("keeps Windows attestations boolean and compares the exact observed page count", async () => {
    const script = await readFile(
      path.join(
        process.cwd(),
        "scripts/template-twin-human-gate/windows-package/run-word-qa.ps1",
      ),
      "utf8",
    );
    expect(script).toContain('if ($answer -eq "Y") { return $true }');
    expect(script).toContain('if ($answer -eq "N") { return $false }');
    expect(script).toContain("[int]$pageAfter -ne $entry.expectedPageCount");
    expect(script).toContain(
      'word-evidence-" + $ShortSha + "-" + $RunTimestamp',
    );
    expect(script).not.toMatch(/function Read-YesNo[\s\S]{0,240}Read-Enum/u);
    expect(script).toContain("Invoke-OpenXmlValidation $reopenedPath");
    expect(script).toContain(
      "$ReportResults[0].sha256 -ne (Get-Sha256 $DocumentPath)",
    );
    expect(script).toContain(
      "[long]$ReportResults[0].sizeBytes -ne (Get-Item -LiteralPath $DocumentPath).Length",
    );
    expect(script).toContain(
      "reopenReadOnlyCompleted = $reopenReadOnlyCompleted",
    );

    const validator = await readFile(
      path.join(
        process.cwd(),
        "scripts/template-twin-human-gate/openxml-validator/Program.cs",
      ),
      "utf8",
    );
    expect(validator).toContain("SHA256.HashData(documentBytes)");
    expect(validator).toContain("sizeBytes = documentBytes.LongLength");
    expect(validator).toContain("WordprocessingDocument.Open(stream, false)");
  });

  it("runs only for the legacy audited branch or explicitly named Template Twin GA releases", async () => {
    const workflow = await readFile(
      path.join(
        process.cwd(),
        "..",
        "..",
        ".github/workflows/template-twin-human-release-gate.yml",
      ),
      "utf8",
    );
    expect(workflow).toContain("name: Template Twin human release gate");
    expect(workflow).toContain(
      "run-name: Template Twin Office review package — human approval remains pending",
    );
    expect(workflow).toContain(
      "name: Synthetic Office and human evidence package",
    );
    expect(workflow).toContain(
      "github.event.pull_request.head.ref == 'feat/template-twin-wm-iov-compatibility-v1'",
    );
    expect(workflow).toContain(
      "startsWith(github.event.pull_request.head.ref, 'release/template-twin-ga-')",
    );
    expect(workflow).toContain(
      "Trusted original package SHA-256 (copy out-of-band for returned-evidence validation)",
    );
    expect(workflow).toContain(
      "^release/template-twin-ga-[0-9]{8}(-[a-z0-9][a-z0-9._-]{0,62})?$",
    );
    expect(workflow).not.toMatch(/if:\s*(?:true|\$\{\{\s*always\(\))/u);
  });
});

describe("human release-gate artifact hygiene", () => {
  let root: string;

  beforeEach(async () => {
    root = await mkdtemp(
      path.join(os.tmpdir(), "template-twin-human-hygiene-"),
    );
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("accepts only the inspected synthetic DOCX/text allowlist", async () => {
    await mkdir(path.join(root, "documents"), { recursive: true });
    const docx = await buildSyntheticDocx();
    await writeFile(
      path.join(root, "documents", "synthetic.source.docx"),
      docx,
    );
    await writeFile(
      path.join(root, "manifest.json"),
      '{"syntheticOnly":true}\n',
    );
    const result = await scanHumanGateDirectory(root);
    expect(result).toMatchObject({ safe: true, filesScanned: 2 });
    expect(result.docxEntriesScanned).toBeGreaterThan(0);
  });

  it("rejects an unexpected VBA/OLE-style binary part before packaging", async () => {
    const docx = await buildSyntheticDocx({
      extraEntries: { "word/vbaProject.bin": new Uint8Array([1, 2, 3, 4]) },
    });
    await writeFile(path.join(root, "synthetic.docx"), docx);
    const result = await scanHumanGateDirectory(root);
    expect(result.safe).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toContain(
      "PRODUCTION_PACKAGE_INSPECTION_FAILED",
    );
  });

  it("rejects an external OPC relationship through the production inspector", async () => {
    const external = syntheticOpc.documentRelationships.replace(
      "</Relationships>",
      '<Relationship Id="remote" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" Target="https://example.test/remote.dotm" TargetMode="External"/></Relationships>',
    );
    const docx = await buildSyntheticDocx({ documentRelationships: external });
    await writeFile(path.join(root, "synthetic.docx"), docx);
    const result = await scanHumanGateDirectory(root);
    expect(result.safe).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toContain(
      "PRODUCTION_PACKAGE_INSPECTION_FAILED",
    );
  });

  it("rejects forbidden source bytes even under a harmless synthetic filename", async () => {
    const bytes = Buffer.from("opaque forbidden source bytes", "utf8");
    await writeFile(path.join(root, "synthetic.txt"), bytes);
    const result = await scanHumanGateDirectory(root, {
      forbiddenFileSha256: [sha256(bytes)],
    });
    expect(result.safe).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toContain(
      "FORBIDDEN_SOURCE_BYTES",
    );
  });

  it("rejects forbidden source markers, non-reserved email addresses, and active PDFs", async () => {
    await writeFile(
      path.join(root, "worksheet.txt"),
      "WM IOV contact person@real.example\n",
    );
    await writeFile(
      path.join(root, "evidence.pdf"),
      "%PDF-1.7\n1 0 obj << /OpenAction 2 0 R >>\n%%EOF",
      "latin1",
    );
    const result = await scanHumanGateDirectory(root);
    expect(result.safe).toBe(false);
    const codes = result.issues.map((issue) => issue.code);
    expect(codes).toContain("FORBIDDEN_WM_IOV_CONTENT");
    expect(codes).toContain("NON_RESERVED_EMAIL_ADDRESS");
    expect(codes).toContain("PDF_ACTIVE_OR_EMBEDDED_CONTENT");
  });

  it("permits only an exact path-and-digest-pinned desktop validator executable", async () => {
    const relativePath = "tools/openxml-validator/OpenXmlValidator.exe";
    const executable = Buffer.from([0x4d, 0x5a, 0, 1, 2, 3, 4]);
    await mkdir(path.join(root, "tools/openxml-validator"), {
      recursive: true,
    });
    await writeFile(path.join(root, relativePath), executable);

    const unbound = await scanHumanGateDirectory(root);
    expect(unbound.safe).toBe(false);
    expect(unbound.issues.map((issue) => issue.code)).toContain(
      "EXECUTABLE_NOT_EXACTLY_ALLOWLISTED",
    );

    const bound = await scanHumanGateDirectory(root, {
      allowedExecutableSha256ByPath: {
        [relativePath]: sha256(executable),
      },
    });
    expect(bound).toMatchObject({ safe: true, issues: [] });
  });
});
