import { execFileSync } from "node:child_process";
import {
  copyFile,
  lstat,
  mkdir,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import JSZip from "jszip";

import { canonicalSha256 } from "../../src/lib/template-twin/canonical";
import {
  EVIDENCE_FILE_HASH_MANIFEST_JSON_SCHEMA,
  HUMAN_GATE_PACKAGE_VERSION,
  WORD_DOCUMENT_MANIFEST_JSON_SCHEMA,
  WORD_HUMAN_EVIDENCE_JSON_SCHEMA,
  WORD_DOCUMENT_MANIFEST_VERSION,
  WORD_OPENXML_VALIDATOR_NAME,
  WORD_OPENXML_VALIDATOR_SDK_VERSION,
  WORD_PDF_EXPORT_BINDING_JSON_SCHEMA,
  WORD_PDF_EXPORT_BINDING_VERSION,
  WORD_VERIFICATION_CONTRACT_VERSION,
  WordQaDocumentManifestSchema,
} from "../../src/lib/template-twin/human-release-gate/contracts";
import {
  scanHumanGateDirectory,
  sha256,
} from "../../src/lib/template-twin/human-release-gate/artifact-hygiene";
import {
  POST_LIBREOFFICE_ARTIFACTS,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
  POST_LIBREOFFICE_TARGETS,
} from "../../src/lib/note-template-docx/office-libreoffice-reviewed-registry";
import {
  assertPostLibreOfficeEvidenceManifest,
  buildPostLibreOfficeEvidenceManifest,
  POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256,
  POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
} from "../../src/lib/note-template-docx/office-post-libreoffice-evidence";

const FIXED_ZIP_DATE = new Date("2000-01-01T00:00:00.000Z");

interface Options {
  readonly inputRoot: string;
  readonly outputRoot: string;
  readonly sourceCommit: string;
  readonly generatedAtIso: string;
}

function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function parseOptions(argv: readonly string[]): Options {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || !value)
      throw new Error("Expected --name value arguments.");
    values.set(key.slice(2), value);
  }
  const inputRoot = values.get("input-root");
  const outputRoot = values.get("output-root");
  const sourceCommit = values.get("source-commit");
  const generatedAtIso = values.get("generated-at");
  invariant(
    typeof inputRoot === "string" &&
      inputRoot.startsWith("/tmp/template-twin-human-gate-"),
    "Input root must use the dedicated /tmp namespace.",
  );
  invariant(
    typeof outputRoot === "string" &&
      outputRoot.startsWith("/tmp/template-twin-human-gate-"),
    "Output root must use the dedicated /tmp namespace.",
  );
  invariant(
    typeof sourceCommit === "string" && /^[a-f0-9]{40}$/u.test(sourceCommit),
    "A full lowercase source commit is required.",
  );
  invariant(
    typeof generatedAtIso === "string" &&
      !Number.isNaN(Date.parse(generatedAtIso)),
    "A deterministic generated-at timestamp is required.",
  );
  return { inputRoot, outputRoot, sourceCommit, generatedAtIso };
}

async function exists(file: string): Promise<boolean> {
  try {
    await lstat(file);
    return true;
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT")
      return false;
    throw error;
  }
}

async function readJson(file: string): Promise<unknown> {
  return JSON.parse((await readFile(file, "utf8")).replace(/^\uFEFF/u, ""));
}

async function writeJson(file: string, value: unknown): Promise<void> {
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function copy(source: string, destination: string): Promise<void> {
  invariant(await exists(source), `Required artifact is missing: ${source}`);
  const metadata = await lstat(source);
  invariant(
    metadata.isFile() && !metadata.isSymbolicLink(),
    `Required artifact is not a regular file: ${source}`,
  );
  await mkdir(path.dirname(destination), { recursive: true });
  await copyFile(source, destination);
}

async function listFiles(root: string): Promise<string[]> {
  const files: string[] = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      const metadata = await lstat(file);
      invariant(!metadata.isSymbolicLink(), `Symlink is forbidden: ${file}`);
      if (metadata.isDirectory()) await walk(file);
      else if (metadata.isFile()) files.push(file);
      else throw new Error(`Non-regular package entry: ${file}`);
    }
  }
  await walk(root);
  return files.sort();
}

function portable(root: string, file: string): string {
  const relative = path.relative(root, file).split(path.sep).join("/");
  invariant(
    relative.length > 0 &&
      !relative.startsWith("/") &&
      !relative.includes("\\") &&
      !relative.split("/").includes(".."),
    `Unsafe package path: ${relative}`,
  );
  return relative;
}

async function deterministicZip(root: string): Promise<Buffer> {
  const zip = new JSZip();
  for (const file of await listFiles(root)) {
    zip.file(portable(root, file), await readFile(file), {
      date: FIXED_ZIP_DATE,
      createFolders: false,
      unixPermissions: 0o100644,
    });
  }
  return zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 9 },
    platform: "UNIX",
  });
}

function repositoryRoot(): string {
  return execFileSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: process.cwd(),
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

async function main(): Promise<void> {
  const options = parseOptions(process.argv.slice(2));
  const shortSha = options.sourceCommit.slice(0, 12);
  const artifactName = `template-twin-human-gate-${shortSha}`;
  const stage = path.join(options.outputRoot, artifactName);
  const outputZip = path.join(options.outputRoot, `${artifactName}.zip`);
  await rm(stage, { recursive: true, force: true });
  await rm(outputZip, { force: true });
  await mkdir(stage, { recursive: true });

  const validatorRelativePath = "tools/openxml-validator/OpenXmlValidator.exe";
  const validatorSource = path.join(
    options.inputRoot,
    "openxml-build",
    "publish-windows",
    "OpenXmlValidator.exe",
  );
  const validatorDestination = path.join(stage, validatorRelativePath);
  await copy(validatorSource, validatorDestination);
  const validatorBytes = await readFile(validatorDestination);
  const validatorSha256 = sha256(validatorBytes);
  const linuxValidatorSha256 = sha256(
    await readFile(
      path.join(
        options.inputRoot,
        "openxml-build",
        "publish-linux",
        "OpenXmlValidator",
      ),
    ),
  );
  invariant(
    linuxValidatorSha256 === POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256 &&
      validatorSha256 === POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
    "Pinned Open XML validator executable identity drifted.",
  );

  const corpusRoot = path.join(options.inputRoot, "corpus");
  const corpusManifest = (await readJson(
    path.join(corpusRoot, "corpus-manifest.json"),
  )) as {
    sourceCommit?: string;
    syntheticOnly?: boolean;
    totals?: {
      failed?: number;
      renderedVerified?: number;
      blockedAsExpected?: number;
    };
    cases?: Array<{
      id: string;
      status: string;
      sourcePath: string;
      outputPath: string | null;
      sourceSha256: string;
      outputSha256: string | null;
      sourceSizeBytes: number;
      outputSizeBytes: number | null;
      expectedPageCount: number | null;
      minimumExpectedPages: number;
    }>;
  };
  invariant(
    corpusManifest.sourceCommit === options.sourceCommit,
    "Corpus source commit mismatch.",
  );
  invariant(
    corpusManifest.syntheticOnly === true,
    "Corpus is not marked synthetic-only.",
  );
  invariant(
    corpusManifest.totals?.failed === 0,
    "Corpus contains a failed case.",
  );
  invariant(
    (corpusManifest.totals?.renderedVerified ?? 0) > 0,
    "Corpus contains no verified output.",
  );
  invariant(
    (corpusManifest.totals?.blockedAsExpected ?? 0) > 0,
    "Corpus contains no fail-closed case.",
  );

  const documents: Array<{
    caseId: string;
    documentRole: "source" | "renderer_output";
    relativePath: string;
    sizeBytes: number;
    sha256: string;
    expectedPageCount: number | null;
    minimumExpectedPages: number;
    verification: {
      contractVersion: typeof WORD_VERIFICATION_CONTRACT_VERSION;
      expectedValueManifest: {
        relativePath: string;
        sizeBytes: number;
        sha256: string;
      };
    };
  }> = [];
  for (const corpusCase of corpusManifest.cases ?? []) {
    invariant(
      /^[a-z0-9][a-z0-9-]{0,79}$/u.test(corpusCase.id),
      "Unsafe corpus case ID.",
    );
    const expectedManifestSource = path.join(
      corpusRoot,
      corpusCase.id,
      "office-expected-manifest.json",
    );
    const expectedManifestRelativePath = `evidence/corpus/${corpusCase.id}/office-expected-manifest.json`;
    const expectedManifestBytes = (await exists(expectedManifestSource))
      ? await readFile(expectedManifestSource)
      : null;
    const expectedValueManifest = expectedManifestBytes
      ? {
          relativePath: expectedManifestRelativePath,
          sizeBytes: expectedManifestBytes.length,
          sha256: sha256(expectedManifestBytes),
        }
      : null;
    // Fail-closed/unsupported corpus cases remain in the package evidence but
    // are not presented to Word as supported compatibility claims: there is no
    // verification-contract-v2 value/static/occurrence manifest for them.
    const roles = expectedValueManifest
      ? [
          {
            documentRole: "source" as const,
            source: corpusCase.sourcePath,
            sha256: corpusCase.sourceSha256,
            sizeBytes: corpusCase.sourceSizeBytes,
          },
          ...(corpusCase.outputPath
            ? [
                {
                  documentRole: "renderer_output" as const,
                  source: corpusCase.outputPath,
                  sha256: corpusCase.outputSha256!,
                  sizeBytes: corpusCase.outputSizeBytes!,
                },
              ]
            : []),
        ]
      : [];
    for (const role of roles) {
      invariant(
        role.source.startsWith(`${corpusRoot}${path.sep}`),
        "Corpus path escaped input root.",
      );
      invariant(
        role.source.endsWith(".docx"),
        "Only DOCX corpus files are permitted.",
      );
      const filename = `${corpusCase.id}.${role.documentRole.replace("_", "-")}.docx`;
      const relativePath = `documents/${corpusCase.id}/${filename}`;
      const destination = path.join(stage, relativePath);
      await copy(role.source, destination);
      const bytes = await readFile(destination);
      invariant(
        sha256(bytes) === role.sha256,
        `${corpusCase.id}: corpus hash mismatch.`,
      );
      invariant(
        bytes.length === role.sizeBytes,
        `${corpusCase.id}: corpus size mismatch.`,
      );
      documents.push({
        caseId: corpusCase.id,
        documentRole: role.documentRole,
        relativePath,
        sizeBytes: bytes.length,
        sha256: sha256(bytes),
        expectedPageCount: corpusCase.expectedPageCount,
        minimumExpectedPages: corpusCase.minimumExpectedPages,
        verification: {
          contractVersion: WORD_VERIFICATION_CONTRACT_VERSION,
          expectedValueManifest: expectedValueManifest!,
        },
      });
    }
    for (const name of [
      "certified-bindings.json",
      "expected-layout.json",
      "expected-values.json",
      "office-expected-manifest.json",
      "output-readback.json",
      "package-inspection.json",
      "static-region-verification.json",
    ]) {
      const source = path.join(corpusRoot, corpusCase.id, name);
      if (await exists(source)) {
        await copy(
          source,
          path.join(stage, "evidence", "corpus", corpusCase.id, name),
        );
      }
    }
  }

  await writeJson(
    path.join(stage, "manifests", "WORD-QA-DOCUMENTS.schema.json"),
    WORD_DOCUMENT_MANIFEST_JSON_SCHEMA,
  );
  await writeJson(
    path.join(stage, "manifests", "WORD-EVIDENCE.schema.json"),
    WORD_HUMAN_EVIDENCE_JSON_SCHEMA,
  );
  await writeJson(
    path.join(stage, "manifests", "RESULT-FILE-HASHES.schema.json"),
    EVIDENCE_FILE_HASH_MANIFEST_JSON_SCHEMA,
  );
  await writeJson(
    path.join(stage, "manifests", "PDF-EXPORT-BINDING.schema.json"),
    WORD_PDF_EXPORT_BINDING_JSON_SCHEMA,
  );
  await copy(
    path.join(corpusRoot, "corpus-manifest.json"),
    path.join(stage, "evidence", "corpus", "corpus-manifest.json"),
  );

  const officeRoot = path.join(options.inputRoot, "office-evidence");
  const libreOffice = (await readJson(
    path.join(officeRoot, "libreoffice-results.json"),
  )) as {
    sourceCommit?: string;
    syntheticOnly?: boolean;
    overallStatus?: string;
    microsoftWordStatus?: string;
    results?: Array<{
      id: string;
      pdfs?: {
        renderer?: { path: string; sha256: string; sizeBytes: number };
        roundtrip?: { path: string; sha256: string; sizeBytes: number };
      };
      visual?: {
        renderer?: {
          visibleText?: { path: string; sha256: string; sizeBytes: number };
        };
        roundtrip?: {
          visibleText?: { path: string; sha256: string; sizeBytes: number };
        };
      };
    }>;
    documentPages?: Array<{
      caseId: string;
      documentRole: "source" | "renderer_output";
      documentSha256: string;
      pageCount: number;
      pdf: { path: string; sha256: string; sizeBytes: number };
      visibleText: { path: string; sha256: string; sizeBytes: number };
    }>;
  };
  invariant(
    libreOffice.sourceCommit === options.sourceCommit &&
      libreOffice.syntheticOnly === true &&
      libreOffice.overallStatus === "passed" &&
      libreOffice.microsoftWordStatus === "PENDING",
    "LibreOffice evidence did not pass or does not match this commit.",
  );
  await copy(
    path.join(officeRoot, "libreoffice-results.json"),
    path.join(stage, "evidence", "office", "libreoffice-results.json"),
  );
  const pageEvidenceByDocument = new Map(
    (libreOffice.documentPages ?? []).map((entry) => [
      `${entry.caseId}:${entry.documentRole}:${entry.documentSha256}`,
      entry,
    ]),
  );
  for (const document of documents) {
    const pageEvidence = pageEvidenceByDocument.get(
      `${document.caseId}:${document.documentRole}:${document.sha256}`,
    );
    invariant(
      pageEvidence &&
        Number.isInteger(pageEvidence.pageCount) &&
        pageEvidence.pageCount > 0,
      "Exact expected page count evidence is missing.",
    );
    document.expectedPageCount = pageEvidence.pageCount;
    const destination = path.join(
      stage,
      "evidence",
      "office",
      "expected-pages",
      document.caseId,
      `${document.documentRole.replace("_", "-")}.pdf`,
    );
    await copy(pageEvidence.pdf.path, destination);
    const bytes = await readFile(destination);
    invariant(
      sha256(bytes) === pageEvidence.pdf.sha256 &&
        bytes.length === pageEvidence.pdf.sizeBytes,
      "Expected page-count PDF evidence mismatch.",
    );
    const visibleTextDestination = destination.replace(
      /\.pdf$/u,
      ".visible-text.txt",
    );
    await copy(pageEvidence.visibleText.path, visibleTextDestination);
    const visibleText = await readFile(visibleTextDestination);
    invariant(
      sha256(visibleText) === pageEvidence.visibleText.sha256 &&
        visibleText.length === pageEvidence.visibleText.sizeBytes,
      "Expected page-count PDF visible-text evidence mismatch.",
    );
  }
  for (const result of libreOffice.results ?? []) {
    invariant(
      /^[a-z0-9][a-z0-9-]{0,79}$/u.test(result.id),
      "Unsafe LibreOffice case ID.",
    );
    for (const [role, evidence] of Object.entries(result.pdfs ?? {})) {
      invariant(
        role === "renderer" || role === "roundtrip",
        "Unexpected LibreOffice PDF role.",
      );
      invariant(
        evidence.path.startsWith(`${officeRoot}${path.sep}`),
        "LibreOffice PDF escaped evidence root.",
      );
      const destination = path.join(
        stage,
        "evidence",
        "office",
        "pdfs",
        result.id,
        `${role}.pdf`,
      );
      await copy(evidence.path, destination);
      const bytes = await readFile(destination);
      invariant(
        sha256(bytes) === evidence.sha256 &&
          bytes.length === evidence.sizeBytes,
        "LibreOffice PDF evidence mismatch.",
      );
      const visibleTextEvidence = result.visual?.[role]?.visibleText;
      invariant(
        visibleTextEvidence,
        "LibreOffice PDF visible-text evidence is missing.",
      );
      const visibleTextDestination = destination.replace(
        /\.pdf$/u,
        ".visible-text.txt",
      );
      await copy(visibleTextEvidence.path, visibleTextDestination);
      const visibleText = await readFile(visibleTextDestination);
      invariant(
        sha256(visibleText) === visibleTextEvidence.sha256 &&
          visibleText.length === visibleTextEvidence.sizeBytes,
        "LibreOffice PDF visible-text evidence mismatch.",
      );
    }
  }
  const openXmlRoot = path.join(officeRoot, "openxml");
  const openXmlSummary = (await readJson(
    path.join(openXmlRoot, "summary.json"),
  )) as {
    sourceCommit?: string;
    syntheticOnly?: boolean;
    Office2013?: string;
    Microsoft365?: string;
  };
  invariant(
    openXmlSummary.sourceCommit === options.sourceCommit &&
      openXmlSummary.syntheticOnly === true &&
      openXmlSummary.Office2013 === "passed" &&
      openXmlSummary.Microsoft365 === "passed",
    "Open XML evidence did not pass or does not match this commit.",
  );
  for (const name of [
    "pre-delivery-Office2013.json",
    "pre-delivery-Microsoft365.json",
    "summary.json",
    "SHA256SUMS.txt",
  ]) {
    await copy(
      path.join(openXmlRoot, name),
      path.join(stage, "evidence", "office", "openxml", name),
    );
  }

  const postLibreOfficeRoot = path.join(officeRoot, "openxml-post-libreoffice");
  const rawPostLibreOfficeReports = await Promise.all(
    POST_LIBREOFFICE_TARGETS.map(async (target) => {
      const relativePath = `post-libreoffice-${target}.json`;
      return {
        relativePath,
        bytes: await readFile(path.join(postLibreOfficeRoot, relativePath)),
      };
    }),
  );
  const savedPostLibreOfficeArtifacts = await Promise.all(
    POST_LIBREOFFICE_ARTIFACTS.map(async (artifact) => {
      const bytes = await readFile(
        path.join(
          officeRoot,
          "cases",
          artifact.caseId,
          "saved",
          artifact.filename,
        ),
      );
      return {
        caseId: artifact.caseId,
        filename: artifact.filename,
        sha256: sha256(bytes),
        sizeBytes: bytes.length,
      };
    }),
  );
  const expectedPostLibreOfficeManifest = buildPostLibreOfficeEvidenceManifest({
    sourceCommit: options.sourceCommit,
    generatedAtIso: options.generatedAtIso,
    validatorExecutableSha256: linuxValidatorSha256,
    windowsValidatorExecutableSha256: validatorSha256,
    libreOfficeResults: {
      relativePath: "libreoffice-results.json",
      bytes: await readFile(path.join(officeRoot, "libreoffice-results.json")),
    },
    rawReports: rawPostLibreOfficeReports,
    savedArtifacts: savedPostLibreOfficeArtifacts,
  });
  const observedPostLibreOfficeManifest = await readJson(
    path.join(postLibreOfficeRoot, "canonical-manifest.json"),
  );
  assertPostLibreOfficeEvidenceManifest(
    observedPostLibreOfficeManifest,
    expectedPostLibreOfficeManifest,
  );
  const observedRegistry = await readJson(
    path.join(postLibreOfficeRoot, "observation-registry.json"),
  );
  invariant(
    canonicalSha256(observedRegistry) ===
      canonicalSha256({
        ...POST_LIBREOFFICE_OBSERVATION_REGISTRY,
        registrySha256: POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
      }),
    "Post-LibreOffice observation registry drifted.",
  );
  const postLibreOfficeFiles = [
    ...rawPostLibreOfficeReports.map((report) => report.relativePath),
    "canonical-manifest.json",
    "observation-registry.json",
  ].sort();
  const expectedPostLibreOfficeSums = (
    await Promise.all(
      postLibreOfficeFiles.map(
        async (name) =>
          `${sha256(await readFile(path.join(postLibreOfficeRoot, name)))}  ${name}`,
      ),
    )
  ).join("\n");
  invariant(
    (
      await readFile(path.join(postLibreOfficeRoot, "SHA256SUMS.txt"), "ascii")
    ).trim() === expectedPostLibreOfficeSums,
    "Post-LibreOffice evidence checksum manifest drifted.",
  );
  for (const name of [...postLibreOfficeFiles, "SHA256SUMS.txt"]) {
    await copy(
      path.join(postLibreOfficeRoot, name),
      path.join(stage, "evidence", "office", "openxml-post-libreoffice", name),
    );
  }

  const documentManifest = WordQaDocumentManifestSchema.parse({
    contractVersion: WORD_DOCUMENT_MANIFEST_VERSION,
    sourceCommit: options.sourceCommit,
    artifactName,
    syntheticOnly: true,
    generatedAtIso: options.generatedAtIso,
    originalsMayBeOpenedByWord: false,
    openXmlValidator: {
      name: WORD_OPENXML_VALIDATOR_NAME,
      sdkVersion: WORD_OPENXML_VALIDATOR_SDK_VERSION,
      executableSha256: validatorSha256,
      targets: ["Office2013", "Microsoft365"],
    },
    documentCount: documents.length,
    documents,
  });
  await writeJson(
    path.join(stage, "manifests", "WORD-QA-DOCUMENTS.json"),
    documentManifest,
  );

  const reviewPacketRoot = path.join(options.inputRoot, "review-packets");
  for (const name of [
    "physician-intent-manifest.json",
    "physician-intent-worksheet.html",
    "physician-intent-decision.schema.json",
    "static-media-review-worksheet.html",
    "static-media-review-evidence.schema.json",
  ]) {
    await copy(
      path.join(reviewPacketRoot, name),
      path.join(stage, "review-packets", name),
    );
  }

  const templateRoot = path.join(
    path.dirname(new URL(import.meta.url).pathname),
    "windows-package",
  );
  for (const name of [
    "README-FIRST.html",
    "RUN-WORD-QA.cmd",
    "VISUAL-CHECKLIST.html",
    "NO-NETWORK-ASSURANCE.txt",
    "CLEANUP-INSTRUCTIONS.txt",
  ]) {
    const template = await readFile(path.join(templateRoot, name), "utf8");
    await writeFile(
      path.join(stage, name),
      template
        .replaceAll("__SOURCE_COMMIT__", options.sourceCommit)
        .replaceAll("__SHORT_SHA__", shortSha),
      "utf8",
    );
  }
  const manifestBytes = await readFile(
    path.join(stage, "manifests", "WORD-QA-DOCUMENTS.json"),
  );
  const powerShellTemplate = await readFile(
    path.join(templateRoot, "run-word-qa.ps1"),
    "utf8",
  );
  await mkdir(path.join(stage, "scripts"), { recursive: true });
  await writeFile(
    path.join(stage, "scripts", "run-word-qa.ps1"),
    powerShellTemplate
      .replaceAll("__SOURCE_COMMIT__", options.sourceCommit)
      .replaceAll("__SHORT_SHA__", shortSha)
      .replaceAll("__MANIFEST_SHA256__", sha256(manifestBytes))
      .replaceAll("__OPENXML_VALIDATOR_SHA256__", validatorSha256)
      .replaceAll(
        "__PDF_EXPORT_BINDING_VERSION__",
        WORD_PDF_EXPORT_BINDING_VERSION,
      ),
    "utf8",
  );

  await writeJson(path.join(stage, "manifests", "PACKAGE.json"), {
    contractVersion: HUMAN_GATE_PACKAGE_VERSION,
    artifactName,
    sourceCommit: options.sourceCommit,
    generatedAtIso: options.generatedAtIso,
    syntheticOnly: true,
    authorizationEffect:
      "none_release_evidence_requires_independent_validation",
    wordStatus: "PENDING_RETURNED_DESKTOP_WORD_EVIDENCE",
    libreOfficeStatus: "passed",
    openXmlPreDeliveryStatus: "passed",
    openXmlPostLibreOfficeStatus: "external_tool_pending_word",
    openXmlPostLibreOfficeSchemaValid: false,
    openXmlPostLibreOfficeSigningEligible: false,
    openXmlPostLibreOfficeReimportEligible: false,
    openXmlPostLibreOfficeCompatibilityEngineeringStatus:
      expectedPostLibreOfficeManifest.compatibilityEngineeringStatus,
    openXmlPostLibreOfficeCompatibilityEngineeringEligible: false,
    openXmlPostLibreOfficeSyntheticReviewerPackageGenerationEligible: true,
    openXmlPostLibreOfficeIndependentReviewStatus:
      expectedPostLibreOfficeManifest.reviewProvenance.independentReviewStatus,
    openXmlPostLibreOfficeEvidenceSha256:
      expectedPostLibreOfficeManifest.evidenceSha256,
    documentCount: documents.length,
    corpusSummary: corpusManifest.totals,
  });

  const root = repositoryRoot();
  invariant(
    execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: root,
      encoding: "utf8",
    }).trim() === options.sourceCommit,
    "Checked-out repository does not match the package source commit.",
  );
  invariant(
    execFileSync("git", ["status", "--porcelain=v1", "--untracked-files=all"], {
      cwd: root,
      encoding: "utf8",
    }).trim().length === 0,
    "Exact-head packaging requires a clean checkout with no untracked inputs.",
  );
  const forbiddenSourceBytes = await readFile(
    path.join(root, "WM IOV Template.docx"),
  );
  const hygiene = await scanHumanGateDirectory(stage, {
    forbiddenFileSha256: [sha256(forbiddenSourceBytes)],
    allowedExecutableSha256ByPath: {
      [validatorRelativePath]: validatorSha256,
    },
  });
  await writeJson(
    path.join(options.outputRoot, `${artifactName}.hygiene.json`),
    hygiene,
  );
  invariant(
    hygiene.safe,
    `Human release-gate hygiene failed: ${hygiene.issues.map((issue) => issue.code).join(",")}`,
  );

  const zipBytes = await deterministicZip(stage);
  await writeFile(outputZip, zipBytes);
  const artifactSha256 = sha256(zipBytes);
  await writeFile(
    `${outputZip}.sha256`,
    `${artifactSha256}  ${path.basename(outputZip)}\n`,
    "ascii",
  );
  await writeJson(
    path.join(options.outputRoot, `${artifactName}.summary.json`),
    {
      artifactName,
      sourceCommit: options.sourceCommit,
      generatedAtIso: options.generatedAtIso,
      syntheticOnly: true,
      artifact: {
        relativePath: path.basename(outputZip),
        sizeBytes: zipBytes.length,
        sha256: artifactSha256,
      },
      documentManifest: {
        relativePath: "manifests/WORD-QA-DOCUMENTS.json",
        sizeBytes: manifestBytes.length,
        sha256: sha256(manifestBytes),
      },
      postLibreOfficeOpenXmlEvidence: {
        relativePath:
          "evidence/office/openxml-post-libreoffice/canonical-manifest.json",
        status: expectedPostLibreOfficeManifest.schemaStatus,
        schemaValid: false,
        signingEligible: false,
        reimportEligible: false,
        compatibilityEngineeringStatus:
          expectedPostLibreOfficeManifest.compatibilityEngineeringStatus,
        compatibilityEngineeringEligible: false,
        syntheticReviewerPackageGenerationEligible: true,
        independentReviewStatus:
          expectedPostLibreOfficeManifest.reviewProvenance
            .independentReviewStatus,
        evidenceSha256: expectedPostLibreOfficeManifest.evidenceSha256,
      },
      hygiene,
      wordStatus: "PENDING_RETURNED_DESKTOP_WORD_EVIDENCE",
    },
  );
  process.stdout.write(
    `${JSON.stringify({ artifactName, outputZip, sizeBytes: zipBytes.length, sha256: artifactSha256 })}\n`,
  );
}

void main();
