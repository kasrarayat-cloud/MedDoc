import { createHash } from "node:crypto";

import JSZip from "jszip";

import {
  EvidenceFileHashManifestSchema,
  type HumanGateValidationIssue,
  type HumanGateValidationReport,
  type HumanGateValidationStatus,
  WordHumanEvidenceSchema,
  WordQaDocumentManifestSchema,
  WORD_OPENXML_VALIDATOR_NAME,
  WORD_OPENXML_VALIDATOR_SDK_VERSION,
} from "./contracts";
import {
  PhysicianIntentManifestSchema,
  WM_IOV_PLACEHOLDER_COUNT,
  validatePhysicianIntentDecisionFile,
} from "../human-gate/physician-intent";
import { validateMediaReviewEvidenceFile } from "../human-gate/media-review";

const MAX_WORD_EVIDENCE_ZIP_BYTES = 256 * 1024 * 1024;
const MAX_ZIP_ENTRIES = 256;
const MAX_ZIP_ENTRY_BYTES = 64 * 1024 * 1024;
const MAX_ZIP_EXPANDED_BYTES = 512 * 1024 * 1024;
const MAX_ZIP_COMPRESSION_RATIO = 200;
const MAX_JSON_BYTES = 8 * 1024 * 1024;
const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_FILE_SIGNATURE = 0x02014b50;
const LOCAL_FILE_SIGNATURE = 0x04034b50;
const FILE_HASH_MANIFEST_PATH = "RESULT-FILE-HASHES.json";
const WORD_EVIDENCE_PATH = "WORD-EVIDENCE.json";
const WORD_DOCUMENT_MANIFEST_PATH = "WORD-QA-DOCUMENTS.json";

interface CentralDirectoryEntry {
  readonly name: string;
  readonly compressedSize: number;
  readonly uncompressedSize: number;
  readonly localHeaderOffset: number;
}

export interface ValidateReturnedHumanGateEvidenceInput {
  readonly expectedSourceCommit: string;
  /**
   * The unmodified package ZIP produced by the exact-head CI run. Its digest
   * must be copied independently from the trusted workflow summary. Returned
   * Word evidence is never allowed to provide its own package trust anchor.
   */
  readonly originalCiPackageZip: Uint8Array;
  readonly expectedOriginalCiPackageZipSha256: string | undefined;
  readonly wordEvidenceZip: Uint8Array;
  /**
   * Digest copied from the adjacent ZIP.sha256 returned by the Word runner.
   * The property is required at the API boundary; `undefined` is represented
   * only so the CLI can return a structured FAIL report when the sidecar is
   * missing instead of crashing before validation.
   */
  readonly expectedWordEvidenceZipSha256: string | undefined;
  readonly physicianManifestJson: Uint8Array;
  readonly physicianDecisionJson: Uint8Array;
  readonly mediaReviewJson: Uint8Array;
  readonly officeArtifactVerifier: ReturnedOfficeArtifactVerifier;
  readonly trustedOpenXmlValidator: TrustedOpenXmlValidator;
  readonly checkedAtIso?: string;
}

export interface ReturnedOfficeArtifactVerifierInput {
  readonly documentRole: "source" | "renderer_output";
  readonly expectedDocumentSha256: string;
  readonly expectedDocumentSizeBytes: number;
  readonly expectedPageCount: number;
  readonly expectedManifestBytes: Uint8Array;
  readonly expectedManifestSha256: string;
  readonly expectedManifestSizeBytes: number;
  readonly workCopyBytes: Uint8Array;
  readonly reopenedDocxBytes: Uint8Array;
  readonly exportedPdfBytes: Uint8Array;
}

export interface ReturnedOfficeArtifactVerification {
  readonly contractVersion: "template-twin-returned-office-artifact-verifier/1.0.0";
  readonly verificationManifestValid: boolean;
  readonly reopenedPackageValid: boolean;
  readonly staticAndOccurrenceValid: boolean;
  readonly semanticReadbackValid: boolean;
  readonly exportedPdfValid: boolean;
}

export type ReturnedOfficeArtifactVerifier = (
  input: ReturnedOfficeArtifactVerifierInput,
) => Promise<ReturnedOfficeArtifactVerification>;

export interface TrustedOpenXmlValidatorInput {
  readonly expectedSourceCommit: string;
  readonly targetFileFormat: "Office2013" | "Microsoft365";
  readonly documentFilename: string;
  readonly documentBytes: Uint8Array;
}

export interface TrustedOpenXmlValidation {
  readonly contractVersion: "template-twin-trusted-openxml-rerun/1.0.0";
  readonly tool: typeof WORD_OPENXML_VALIDATOR_NAME;
  readonly sdkVersion: typeof WORD_OPENXML_VALIDATOR_SDK_VERSION;
  readonly validatorSourceCommit: string;
  readonly validatorExecutableSha256: string;
  readonly returnedExecutableUsed: false;
  readonly networkModeDuringValidation: "none";
  readonly targetFileFormat: "Office2013" | "Microsoft365";
  readonly documentFilename: string;
  readonly documentSha256: string;
  readonly documentSizeBytes: number;
  readonly valid: boolean;
  readonly errorCount: number;
}

export type TrustedOpenXmlValidator = (
  input: TrustedOpenXmlValidatorInput,
) => Promise<TrustedOpenXmlValidation>;

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function addIssue(
  issues: HumanGateValidationIssue[],
  code: string,
  status: Exclude<HumanGateValidationStatus, "PASS">,
  message: string,
): void {
  if (issues.some((issue) => issue.code === code && issue.message === message))
    return;
  issues.push({ code, status, message });
}

function safeZipPath(name: string): boolean {
  return (
    name.length > 0 &&
    name.length <= 500 &&
    !name.startsWith("/") &&
    !name.includes("\\") &&
    !name.includes("\0") &&
    !/^[A-Za-z]:/u.test(name) &&
    !name.endsWith("/") &&
    !name
      .split("/")
      .some(
        (segment) => segment === "" || segment === "." || segment === "..",
      ) &&
    /^[\x20-\x7e]+$/u.test(name)
  );
}

function findEndOfCentralDirectory(bytes: Buffer): number {
  const minimumOffset = Math.max(0, bytes.length - 65_557);
  for (let offset = bytes.length - 22; offset >= minimumOffset; offset -= 1) {
    if (bytes.readUInt32LE(offset) !== EOCD_SIGNATURE) continue;
    const commentLength = bytes.readUInt16LE(offset + 20);
    if (offset + 22 + commentLength === bytes.length) return offset;
  }
  throw new Error("TT_HUMAN_GATE_ZIP_EOCD_INVALID");
}

/**
 * Parses the ZIP central directory before JSZip is allowed to inflate bytes.
 * This detects duplicate names that JSZip's object view would otherwise hide,
 * rejects ZIP64/encryption/traversal, and bounds aggregate expansion.
 */
function inspectZipCentralDirectory(bytes: Buffer): CentralDirectoryEntry[] {
  if (bytes.length === 0 || bytes.length > MAX_WORD_EVIDENCE_ZIP_BYTES) {
    throw new Error("TT_HUMAN_GATE_ZIP_SIZE_LIMIT");
  }
  const eocd = findEndOfCentralDirectory(bytes);
  const diskNumber = bytes.readUInt16LE(eocd + 4);
  const centralDisk = bytes.readUInt16LE(eocd + 6);
  const diskEntries = bytes.readUInt16LE(eocd + 8);
  const totalEntries = bytes.readUInt16LE(eocd + 10);
  const centralSize = bytes.readUInt32LE(eocd + 12);
  const centralOffset = bytes.readUInt32LE(eocd + 16);
  if (
    diskNumber !== 0 ||
    centralDisk !== 0 ||
    diskEntries !== totalEntries ||
    totalEntries === 0 ||
    totalEntries === 0xffff ||
    centralSize === 0xffffffff ||
    centralOffset === 0xffffffff
  ) {
    throw new Error("TT_HUMAN_GATE_ZIP_MULTIDISK_OR_ZIP64");
  }
  if (totalEntries > MAX_ZIP_ENTRIES || centralOffset + centralSize !== eocd) {
    throw new Error("TT_HUMAN_GATE_ZIP_DIRECTORY_LIMIT");
  }

  const entries: CentralDirectoryEntry[] = [];
  const names = new Set<string>();
  const foldedNames = new Set<string>();
  let totalExpanded = 0;
  let offset = centralOffset;
  for (let index = 0; index < totalEntries; index += 1) {
    if (
      offset + 46 > eocd ||
      bytes.readUInt32LE(offset) !== CENTRAL_FILE_SIGNATURE
    ) {
      throw new Error("TT_HUMAN_GATE_ZIP_DIRECTORY_INVALID");
    }
    const flags = bytes.readUInt16LE(offset + 8);
    const compressionMethod = bytes.readUInt16LE(offset + 10);
    const compressedSize = bytes.readUInt32LE(offset + 20);
    const uncompressedSize = bytes.readUInt32LE(offset + 24);
    const nameLength = bytes.readUInt16LE(offset + 28);
    const extraLength = bytes.readUInt16LE(offset + 30);
    const commentLength = bytes.readUInt16LE(offset + 32);
    const localHeaderOffset = bytes.readUInt32LE(offset + 42);
    const entryEnd = offset + 46 + nameLength + extraLength + commentLength;
    if (
      entryEnd > eocd ||
      nameLength === 0 ||
      compressedSize === 0xffffffff ||
      uncompressedSize === 0xffffffff ||
      localHeaderOffset === 0xffffffff ||
      (flags & 0x0001) !== 0 ||
      (flags & 0x0040) !== 0 ||
      ![0, 8].includes(compressionMethod)
    ) {
      throw new Error("TT_HUMAN_GATE_ZIP_ENTRY_UNSUPPORTED");
    }
    const name = bytes
      .subarray(offset + 46, offset + 46 + nameLength)
      .toString("utf8");
    const foldedName = name.toLocaleLowerCase("en-US");
    if (!safeZipPath(name) || names.has(name) || foldedNames.has(foldedName)) {
      throw new Error("TT_HUMAN_GATE_ZIP_PATH_OR_DUPLICATE");
    }
    if (
      uncompressedSize > MAX_ZIP_ENTRY_BYTES ||
      (compressedSize === 0 && uncompressedSize > 0) ||
      (compressedSize > 0 &&
        uncompressedSize / compressedSize > MAX_ZIP_COMPRESSION_RATIO)
    ) {
      throw new Error("TT_HUMAN_GATE_ZIP_EXPANSION_LIMIT");
    }
    totalExpanded += uncompressedSize;
    if (
      totalExpanded > MAX_ZIP_EXPANDED_BYTES ||
      localHeaderOffset + 4 > centralOffset ||
      bytes.readUInt32LE(localHeaderOffset) !== LOCAL_FILE_SIGNATURE
    ) {
      throw new Error("TT_HUMAN_GATE_ZIP_EXPANSION_OR_LOCAL_HEADER");
    }
    names.add(name);
    foldedNames.add(foldedName);
    entries.push({ name, compressedSize, uncompressedSize, localHeaderOffset });
    offset = entryEnd;
  }
  if (offset !== eocd)
    throw new Error("TT_HUMAN_GATE_ZIP_DIRECTORY_TRAILING_DATA");
  return entries;
}

function parseJsonBytes(bytes: Uint8Array, label: string): unknown {
  if (bytes.byteLength === 0 || bytes.byteLength > MAX_JSON_BYTES) {
    throw new Error(`${label}_SIZE_LIMIT`);
  }
  const text = Buffer.from(bytes)
    .toString("utf8")
    .replace(/^\uFEFF/u, "");
  return JSON.parse(text) as unknown;
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function exactObjectKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    actual.length === sortedExpected.length &&
    actual.every((key, index) => key === sortedExpected[index])
  );
}

async function loadTrustedOriginalPackageManifest(input: {
  readonly bytes: Buffer;
  readonly expectedZipSha256: string | undefined;
  readonly expectedSourceCommit: string;
  readonly issues: HumanGateValidationIssue[];
}): Promise<Buffer | null> {
  const actualZipSha256 = sha256(input.bytes);
  if (input.expectedZipSha256 === undefined) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_ORIGINAL_CI_PACKAGE_HASH_MISSING",
      "FAIL",
      "The original CI package is missing the trusted SHA-256 copied out-of-band from the exact-head workflow summary.",
    );
    return null;
  }
  if (
    !/^[a-f0-9]{64}$/u.test(input.expectedZipSha256) ||
    input.expectedZipSha256 !== actualZipSha256
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_ORIGINAL_CI_PACKAGE_HASH_MISMATCH",
      "FAIL",
      "The supplied original CI package does not match its independently trusted workflow digest.",
    );
    return null;
  }

  let centralEntries: CentralDirectoryEntry[];
  try {
    centralEntries = inspectZipCentralDirectory(input.bytes);
  } catch (error) {
    addIssue(
      input.issues,
      errorCode(error, "TT_HUMAN_GATE_ORIGINAL_CI_PACKAGE_INVALID"),
      "FAIL",
      "The digest-bound original CI package failed bounded structural inspection.",
    );
    return null;
  }

  const artifactName = `template-twin-human-gate-${input.expectedSourceCommit.slice(0, 12)}`;
  const expectedManifestPath = `manifests/${WORD_DOCUMENT_MANIFEST_PATH}`;
  const manifestCandidates = centralEntries.filter(
    (entry) =>
      entry.name === expectedManifestPath ||
      entry.name.endsWith(`/manifests/${WORD_DOCUMENT_MANIFEST_PATH}`),
  );
  if (
    manifestCandidates.length !== 1 ||
    manifestCandidates[0]?.name !== expectedManifestPath ||
    manifestCandidates[0].uncompressedSize > MAX_JSON_BYTES
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_ORIGINAL_CI_MANIFEST_MISSING",
      "FAIL",
      "The trusted original CI package lacks the one exact-head Word document manifest at its deterministic path.",
    );
    return null;
  }

  try {
    const zip = await JSZip.loadAsync(input.bytes, {
      checkCRC32: true,
      createFolders: false,
    });
    const entry = zip.file(expectedManifestPath);
    if (!entry) throw new Error("missing");
    const manifestBytes = await entry.async("nodebuffer");
    if (manifestBytes.length !== manifestCandidates[0].uncompressedSize) {
      throw new Error("size");
    }
    const manifest = WordQaDocumentManifestSchema.parse(
      parseJsonBytes(
        manifestBytes,
        "TT_HUMAN_GATE_TRUSTED_ORIGINAL_WORD_MANIFEST",
      ),
    );
    if (
      manifest.sourceCommit !== input.expectedSourceCommit ||
      manifest.artifactName !== artifactName
    ) {
      throw new Error("identity");
    }
    return manifestBytes;
  } catch {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_ORIGINAL_CI_MANIFEST_INVALID",
      "FAIL",
      "The exact manifest inside the digest-bound original CI package is malformed or belongs to another release head.",
    );
    return null;
  }
}

function validOpenXmlReport(input: {
  readonly bytes: Uint8Array;
  readonly expectedSourceCommit: string;
  readonly expectedValidatorSha256: string;
  readonly expectedTarget: "Office2013" | "Microsoft365";
  readonly expectedDocumentFilename: string;
  readonly expectedDocumentSha256: string;
  readonly expectedDocumentSizeBytes: number;
}): boolean {
  try {
    const report = objectRecord(
      parseJsonBytes(input.bytes, "TT_HUMAN_GATE_OPENXML_REPORT"),
    );
    if (
      !report ||
      !exactObjectKeys(report, [
        "tool",
        "sdkVersion",
        "packageVersion",
        "validatorExecutableSha256",
        "targetFileFormat",
        "sourceCommit",
        "generatedAt",
        "results",
      ]) ||
      report.tool !== WORD_OPENXML_VALIDATOR_NAME ||
      report.sdkVersion !== WORD_OPENXML_VALIDATOR_SDK_VERSION ||
      typeof report.packageVersion !== "string" ||
      !/^3\.5\.1(?:\+|$)/u.test(report.packageVersion) ||
      report.validatorExecutableSha256 !== input.expectedValidatorSha256 ||
      report.targetFileFormat !== input.expectedTarget ||
      report.sourceCommit !== input.expectedSourceCommit ||
      typeof report.generatedAt !== "string" ||
      Number.isNaN(Date.parse(report.generatedAt)) ||
      !Array.isArray(report.results) ||
      report.results.length !== 1
    ) {
      return false;
    }
    const result = objectRecord(report.results[0]);
    return Boolean(
      result &&
      exactObjectKeys(result, [
        "file",
        "sha256",
        "sizeBytes",
        "opened",
        "valid",
        "errorCount",
        "errors",
      ]) &&
      result.file === input.expectedDocumentFilename &&
      result.sha256 === input.expectedDocumentSha256 &&
      result.sizeBytes === input.expectedDocumentSizeBytes &&
      result.opened === true &&
      result.valid === true &&
      result.errorCount === 0 &&
      Array.isArray(result.errors) &&
      result.errors.length === 0,
    );
  } catch {
    return false;
  }
}

function validTrustedOpenXmlRerun(input: {
  readonly validation: TrustedOpenXmlValidation;
  readonly expectedSourceCommit: string;
  readonly expectedTarget: "Office2013" | "Microsoft365";
  readonly expectedDocumentFilename: string;
  readonly expectedDocumentSha256: string;
  readonly expectedDocumentSizeBytes: number;
}): boolean {
  const validation = input.validation;
  return Boolean(
    validation.contractVersion ===
      "template-twin-trusted-openxml-rerun/1.0.0" &&
    validation.tool === WORD_OPENXML_VALIDATOR_NAME &&
    validation.sdkVersion === WORD_OPENXML_VALIDATOR_SDK_VERSION &&
    validation.validatorSourceCommit === input.expectedSourceCommit &&
    /^[a-f0-9]{64}$/u.test(validation.validatorExecutableSha256) &&
    validation.returnedExecutableUsed === false &&
    validation.networkModeDuringValidation === "none" &&
    validation.targetFileFormat === input.expectedTarget &&
    validation.documentFilename === input.expectedDocumentFilename &&
    validation.documentSha256 === input.expectedDocumentSha256 &&
    validation.documentSizeBytes === input.expectedDocumentSizeBytes &&
    validation.valid === true &&
    validation.errorCount === 0,
  );
}

function statusFromIssues(
  issues: readonly HumanGateValidationIssue[],
): HumanGateValidationStatus {
  if (issues.some((issue) => issue.status === "FAIL")) return "FAIL";
  if (issues.some((issue) => issue.status === "BLOCKED")) return "BLOCKED";
  return "PASS";
}

function errorCode(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const match = error.message.match(/^(TT_[A-Z0-9_]+)/u);
    if (match) return match[1];
  }
  return fallback;
}

async function validateWordEvidence(input: {
  readonly bytes: Buffer;
  readonly originalCiPackageBytes: Buffer;
  readonly expectedOriginalCiPackageZipSha256: string | undefined;
  readonly expectedSourceCommit: string;
  readonly expectedZipSha256: string | undefined;
  readonly officeArtifactVerifier: ReturnedOfficeArtifactVerifier;
  readonly trustedOpenXmlValidator: TrustedOpenXmlValidator;
  readonly issues: HumanGateValidationIssue[];
}): Promise<void> {
  const trustedOriginalManifestBytes = await loadTrustedOriginalPackageManifest(
    {
      bytes: input.originalCiPackageBytes,
      expectedZipSha256: input.expectedOriginalCiPackageZipSha256,
      expectedSourceCommit: input.expectedSourceCommit,
      issues: input.issues,
    },
  );
  const zipSha256 = sha256(input.bytes);
  if (input.expectedZipSha256 === undefined) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ZIP_HASH_MISSING",
      "FAIL",
      "The returned Word evidence ZIP is missing its required adjacent SHA-256 sidecar.",
    );
  } else if (
    !/^[a-f0-9]{64}$/u.test(input.expectedZipSha256) ||
    input.expectedZipSha256 !== zipSha256
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ZIP_HASH_MISMATCH",
      "FAIL",
      "The returned Word evidence ZIP does not match its supplied SHA-256.",
    );
  }

  let centralEntries: CentralDirectoryEntry[];
  try {
    centralEntries = inspectZipCentralDirectory(input.bytes);
  } catch (error) {
    addIssue(
      input.issues,
      errorCode(error, "TT_HUMAN_GATE_WORD_ZIP_INVALID"),
      "FAIL",
      "The returned Word evidence ZIP failed bounded structural inspection.",
    );
    return;
  }

  let zip: JSZip;
  try {
    zip = await JSZip.loadAsync(input.bytes, {
      checkCRC32: true,
      createFolders: false,
    });
  } catch {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ZIP_CRC_INVALID",
      "FAIL",
      "The returned Word evidence ZIP failed decompression or CRC verification.",
    );
    return;
  }
  const centralNames = centralEntries.map((entry) => entry.name).sort();
  const jsZipNames = Object.values(zip.files)
    .filter((entry) => !entry.dir)
    .map((entry) => entry.name)
    .sort();
  if (
    centralNames.length !== jsZipNames.length ||
    centralNames.some((name, index) => name !== jsZipNames[index])
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ZIP_ENTRY_VIEW_MISMATCH",
      "FAIL",
      "ZIP entry identities changed between structural inspection and decompression.",
    );
    return;
  }

  const required = [
    FILE_HASH_MANIFEST_PATH,
    WORD_EVIDENCE_PATH,
    WORD_DOCUMENT_MANIFEST_PATH,
  ];
  if (required.some((name) => !zip.file(name))) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_REQUIRED_FILE_MISSING",
      "FAIL",
      "The returned Word evidence ZIP is missing a required manifest or evidence file.",
    );
    return;
  }

  const inflated = new Map<string, Buffer>();
  try {
    for (const entry of centralEntries) {
      const file = zip.file(entry.name);
      if (!file) throw new Error("missing");
      const bytes = await file.async("nodebuffer");
      if (bytes.length !== entry.uncompressedSize) throw new Error("size");
      inflated.set(entry.name, bytes);
    }
  } catch {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ZIP_INFLATE_MISMATCH",
      "FAIL",
      "An evidence file did not match the bounded ZIP metadata.",
    );
    return;
  }

  let hashManifest: ReturnType<typeof EvidenceFileHashManifestSchema.parse>;
  let documentManifest: ReturnType<typeof WordQaDocumentManifestSchema.parse>;
  let wordEvidence: ReturnType<typeof WordHumanEvidenceSchema.parse>;
  try {
    hashManifest = EvidenceFileHashManifestSchema.parse(
      parseJsonBytes(
        inflated.get(FILE_HASH_MANIFEST_PATH)!,
        "TT_HUMAN_GATE_HASH_MANIFEST",
      ),
    );
    documentManifest = WordQaDocumentManifestSchema.parse(
      parseJsonBytes(
        inflated.get(WORD_DOCUMENT_MANIFEST_PATH)!,
        "TT_HUMAN_GATE_WORD_MANIFEST",
      ),
    );
    wordEvidence = WordHumanEvidenceSchema.parse(
      parseJsonBytes(
        inflated.get(WORD_EVIDENCE_PATH)!,
        "TT_HUMAN_GATE_WORD_EVIDENCE",
      ),
    );
  } catch {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_SCHEMA_INVALID",
      "FAIL",
      "A Word evidence manifest does not satisfy its strict schema.",
    );
    return;
  }

  const hashedPaths = new Set(
    hashManifest.files.map((entry) => entry.relativePath),
  );
  const expectedHashedPaths = centralNames.filter(
    (name) => name !== FILE_HASH_MANIFEST_PATH,
  );
  if (
    hashedPaths.size !== expectedHashedPaths.length ||
    expectedHashedPaths.some((name) => !hashedPaths.has(name))
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_HASH_COVERAGE_MISMATCH",
      "FAIL",
      "The internal hash manifest does not cover every returned evidence file exactly once.",
    );
  }
  for (const entry of hashManifest.files) {
    const bytes = inflated.get(entry.relativePath);
    if (
      !bytes ||
      bytes.length !== entry.sizeBytes ||
      sha256(bytes) !== entry.sha256
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_FILE_HASH_MISMATCH",
        "FAIL",
        "At least one returned evidence file was missing, changed, or truncated.",
      );
      break;
    }
  }

  if (
    documentManifest.sourceCommit !== input.expectedSourceCommit ||
    wordEvidence.sourceCommit !== input.expectedSourceCommit ||
    documentManifest.artifactName !==
      `template-twin-human-gate-${input.expectedSourceCommit.slice(0, 12)}`
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_SOURCE_MISMATCH",
      "FAIL",
      "Word evidence belongs to a different Template Twin commit or package.",
    );
  }
  const manifestBytes = inflated.get(WORD_DOCUMENT_MANIFEST_PATH)!;
  if (
    trustedOriginalManifestBytes &&
    !Buffer.from(manifestBytes).equals(trustedOriginalManifestBytes)
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_TRUSTED_MANIFEST_MISMATCH",
      "FAIL",
      "The returned Word evidence contains a self-consistent replacement manifest instead of the manifest authenticated by the original exact-head CI package digest.",
    );
  }
  if (wordEvidence.packageManifestSha256 !== sha256(manifestBytes)) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_PACKAGE_MANIFEST_MISMATCH",
      "FAIL",
      "Word evidence is not bound to the package document manifest contained in the ZIP.",
    );
  }

  const manifestByKey = new Map<
    string,
    (typeof documentManifest.documents)[number]
  >();
  for (const document of documentManifest.documents) {
    const key = `${document.caseId}\0${document.documentRole}`;
    if (manifestByKey.has(key)) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_DUPLICATE_DOCUMENT",
        "FAIL",
        "The package manifest contains a duplicate document identity.",
      );
    }
    manifestByKey.set(key, document);
  }

  if (!wordEvidence.attestation.reviewedOnlySyntheticDocuments) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_NON_SYNTHETIC_ATTESTATION",
      "FAIL",
      "The Word reviewer did not attest that only the allowlisted synthetic documents were reviewed.",
    );
  }
  if (
    !wordEvidence.attestation.observedRepairDialogsInDesktopWord ||
    !wordEvidence.attestation.completedVisualChecklistForEveryDocument ||
    !wordEvidence.attestation.understandsAutomationCannotJudgeVisualCorrectness
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_ATTESTATION_INCOMPLETE",
      "BLOCKED",
      "One or more required desktop Word human-review attestations remain incomplete.",
    );
  }

  const evidenceKeys = new Set<string>();
  const generatedPaths = new Set<string>();
  for (const evidence of wordEvidence.documents) {
    const key = `${evidence.caseId}\0${evidence.documentRole}`;
    if (evidenceKeys.has(key)) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_DUPLICATE_DOCUMENT_EVIDENCE",
        "FAIL",
        "The returned evidence contains a duplicate document identity.",
      );
      continue;
    }
    evidenceKeys.add(key);
    const expected = manifestByKey.get(key);
    if (
      !expected ||
      evidence.allowlistedRelativePath !== expected.relativePath ||
      evidence.originalExpectedSha256 !== expected.sha256 ||
      evidence.originalExpectedSizeBytes !== expected.sizeBytes ||
      evidence.expectedPageCount !== expected.expectedPageCount ||
      evidence.minimumExpectedPages !== expected.minimumExpectedPages
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_DOCUMENT_MISMATCH",
        "FAIL",
        "Returned evidence does not match an exact allowlisted package document.",
      );
      continue;
    }
    if (
      !evidence.originalUnchanged ||
      evidence.originalBeforeSha256 !== expected.sha256 ||
      evidence.originalAfterSha256 !== expected.sha256
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_ORIGINAL_CHANGED",
        "FAIL",
        "Microsoft Word QA did not preserve the immutable synthetic original.",
      );
    }
    if (evidence.automationStatus === "FAILED") {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_AUTOMATION_FAILED",
        "FAIL",
        "Desktop Word automation failed for at least one document.",
      );
    } else if (
      evidence.automationStatus !== "COMPLETED" ||
      evidence.automationErrorCode !== "NONE"
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_AUTOMATION_BLOCKED",
        "BLOCKED",
        "Desktop Word automation was unavailable or incomplete for at least one document.",
      );
    }
    if (
      !evidence.saveAsCompleted ||
      !evidence.reopenReadOnlyCompleted ||
      !evidence.pdfExportCompleted
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_SAVE_REOPEN_EXPORT_INCOMPLETE",
        "FAIL",
        "Desktop Word did not prove save-as, read-only reopen, and PDF export for every document.",
      );
    }
    if (
      evidence.pageCountAfterReopen === null ||
      evidence.pageCountAfterReopen < expected.minimumExpectedPages
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_PAGE_COUNT_INCOMPLETE",
        evidence.pageCountAfterReopen === null ? "BLOCKED" : "FAIL",
        "A reopened Word document lacks acceptable page-count evidence.",
      );
    }
    if (
      !evidence.pageCountMatchesExpected ||
      evidence.pageCountAfterReopen !== expected.expectedPageCount
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_PAGE_COUNT_MISMATCH",
        "FAIL",
        "A reopened Word document does not match its exact expected page count.",
      );
    }

    const safeStem = `${evidence.caseId}--${evidence.documentRole}`;
    const expectedGeneratedPaths = new Map<
      (typeof evidence.generatedFiles)[number]["kind"],
      string
    >([
      ["work_copy", `work-copies/${safeStem}.work-copy.docx`],
      [
        "word_reopened_docx",
        `word-reopened-docx/${safeStem}.word-reopened.docx`,
      ],
      ["word_exported_pdf", `word-exported-pdf/${safeStem}.word.pdf`],
      ["openxml_office2013_json", `openxml/${safeStem}.Office2013.json`],
      ["openxml_microsoft365_json", `openxml/${safeStem}.Microsoft365.json`],
    ]);
    const generatedByKind = new Map(
      evidence.generatedFiles.map((file) => [file.kind, file]),
    );
    const generatedKinds = new Set(generatedByKind.keys());
    if (
      evidence.generatedFiles.length !== expectedGeneratedPaths.size ||
      generatedKinds.size !== expectedGeneratedPaths.size ||
      [...expectedGeneratedPaths.keys()].some(
        (kind) => !generatedKinds.has(kind),
      )
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_GENERATED_EVIDENCE_INCOMPLETE",
        "FAIL",
        "Each Word document must have one work copy, reopened DOCX, exported PDF, and two target-specific Open XML reports.",
      );
    }
    for (const generated of evidence.generatedFiles) {
      if (
        expectedGeneratedPaths.get(generated.kind) !== generated.relativePath ||
        generatedPaths.has(generated.relativePath)
      ) {
        addIssue(
          input.issues,
          "TT_HUMAN_GATE_WORD_GENERATED_PATH_MISMATCH",
          "FAIL",
          "A generated evidence path is not the exact path for its document identity or was reused.",
        );
      }
      generatedPaths.add(generated.relativePath);
      const bytes = inflated.get(generated.relativePath);
      if (
        !bytes ||
        bytes.length !== generated.sizeBytes ||
        sha256(bytes) !== generated.sha256
      ) {
        addIssue(
          input.issues,
          "TT_HUMAN_GATE_WORD_GENERATED_FILE_MISMATCH",
          "FAIL",
          "A generated Word evidence file is missing or does not match its recorded hash.",
        );
        continue;
      }
      if (
        generated.kind === "work_copy" &&
        (generated.sha256 !== expected.sha256 ||
          generated.sizeBytes !== expected.sizeBytes)
      ) {
        addIssue(
          input.issues,
          "TT_HUMAN_GATE_WORD_WORK_COPY_MISMATCH",
          "FAIL",
          "The disposable Word work copy does not match the immutable package document.",
        );
      }
    }

    const expectedManifestFile = expected.verification.expectedValueManifest;
    const expectedManifestBytes = inflated.get(
      expectedManifestFile.relativePath,
    );
    const workCopy = generatedByKind.get("work_copy");
    const reopened = generatedByKind.get("word_reopened_docx");
    const exportedPdf = generatedByKind.get("word_exported_pdf");
    let artifactVerification: ReturnedOfficeArtifactVerification;
    try {
      artifactVerification = await input.officeArtifactVerifier({
        documentRole: evidence.documentRole,
        expectedDocumentSha256: expected.sha256,
        expectedDocumentSizeBytes: expected.sizeBytes,
        expectedPageCount: expected.expectedPageCount,
        expectedManifestBytes: expectedManifestBytes ?? new Uint8Array(),
        expectedManifestSha256: expectedManifestFile.sha256,
        expectedManifestSizeBytes: expectedManifestFile.sizeBytes,
        workCopyBytes: workCopy
          ? (inflated.get(workCopy.relativePath) ?? new Uint8Array())
          : new Uint8Array(),
        reopenedDocxBytes: reopened
          ? (inflated.get(reopened.relativePath) ?? new Uint8Array())
          : new Uint8Array(),
        exportedPdfBytes: exportedPdf
          ? (inflated.get(exportedPdf.relativePath) ?? new Uint8Array())
          : new Uint8Array(),
      });
    } catch {
      artifactVerification = {
        contractVersion:
          "template-twin-returned-office-artifact-verifier/1.0.0",
        verificationManifestValid: false,
        reopenedPackageValid: false,
        staticAndOccurrenceValid: false,
        semanticReadbackValid: false,
        exportedPdfValid: false,
      };
    }
    if (
      artifactVerification.contractVersion !==
        "template-twin-returned-office-artifact-verifier/1.0.0" ||
      !artifactVerification.verificationManifestValid
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_VERIFICATION_MANIFEST_INVALID",
        "FAIL",
        "The exact verification-contract-v2 expected-value manifest is missing, invalid, or belongs to another document.",
      );
    }
    if (!artifactVerification.reopenedPackageValid) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_REOPENED_PACKAGE_INVALID",
        "FAIL",
        "The reopened Word file failed the production OPC/XML/security package inspector.",
      );
    }
    if (!artifactVerification.staticAndOccurrenceValid) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_STATIC_OR_OCCURRENCE_MISMATCH",
        "FAIL",
        "The reopened Word file did not preserve every normalized static region and unique certified field occurrence.",
      );
    }
    if (
      evidence.documentRole === "renderer_output" &&
      !artifactVerification.semanticReadbackValid
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_SEMANTIC_READBACK_MISMATCH",
        "FAIL",
        "The reopened Word renderer output failed exact semantic value, control-state, binding, or occurrence readback.",
      );
    }
    if (!artifactVerification.exportedPdfValid) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_EXPORTED_PDF_INVALID",
        "FAIL",
        "The Word-exported PDF is malformed, active, encrypted, or has the wrong page count.",
      );
    }

    const reopenedFilename = `${safeStem}.word-reopened.docx`;
    const reopenedBytes = reopened
      ? (inflated.get(reopened.relativePath) ?? new Uint8Array())
      : new Uint8Array();
    const reopenedSha256 = sha256(reopenedBytes);
    for (const [kind, target] of [
      ["openxml_office2013_json", "Office2013"],
      ["openxml_microsoft365_json", "Microsoft365"],
    ] as const) {
      const report = generatedByKind.get(kind);
      if (
        !report ||
        !validOpenXmlReport({
          bytes: inflated.get(report.relativePath) ?? new Uint8Array(),
          expectedSourceCommit: input.expectedSourceCommit,
          expectedValidatorSha256:
            documentManifest.openXmlValidator.executableSha256,
          expectedTarget: target,
          expectedDocumentFilename: reopenedFilename,
          expectedDocumentSha256: reopenedSha256,
          expectedDocumentSizeBytes: reopenedBytes.byteLength,
        })
      ) {
        addIssue(
          input.issues,
          "TT_HUMAN_GATE_WORD_OPENXML_SCHEMA_INVALID",
          "FAIL",
          `The reopened Word file lacks a passing ${target} Open XML SDK result from the pinned validator.`,
        );
      }

      if (reopenedBytes.byteLength === 0) continue;
      try {
        const trustedValidation = await input.trustedOpenXmlValidator({
          expectedSourceCommit: input.expectedSourceCommit,
          targetFileFormat: target,
          documentFilename: reopenedFilename,
          documentBytes: reopenedBytes,
        });
        if (
          !validTrustedOpenXmlRerun({
            validation: trustedValidation,
            expectedSourceCommit: input.expectedSourceCommit,
            expectedTarget: target,
            expectedDocumentFilename: reopenedFilename,
            expectedDocumentSha256: reopenedSha256,
            expectedDocumentSizeBytes: reopenedBytes.byteLength,
          })
        ) {
          addIssue(
            input.issues,
            "TT_HUMAN_GATE_WORD_TRUSTED_OPENXML_RERUN_INVALID",
            "FAIL",
            `The exact returned DOCX bytes failed the source-built trusted ${target} Open XML rerun or its byte identity did not match.`,
          );
        }
      } catch {
        addIssue(
          input.issues,
          "TT_HUMAN_GATE_WORD_TRUSTED_OPENXML_RERUN_BLOCKED",
          "BLOCKED",
          `The required source-built trusted ${target} Open XML rerun could not be completed; returned executables and reports cannot substitute for it.`,
        );
      }
    }

    const observation = evidence.humanObservation;
    if (observation.repairDialog === "REPAIR_DIALOG_SHOWN") {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_REPAIR_DIALOG",
        "FAIL",
        "A human reviewer observed a repair, corruption, or conversion-loss dialog.",
      );
    } else if (observation.repairDialog !== "NO_REPAIR_DIALOG") {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_REPAIR_NOT_OBSERVED",
        "BLOCKED",
        "A human reviewer did not observe Word for repair dialogs.",
      );
    }
    const humanResults = [
      observation.visibleClinicalValues,
      observation.controlBehavior,
      observation.duplicateOrMissingFields,
      observation.clinicallyMeaningfulStaticText,
      observation.tablesHeadersAndFooters,
      observation.marginsFontsAndPagination,
      observation.overall,
    ];
    if (humanResults.includes("FAIL")) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_HUMAN_REVIEW_FAILED",
        "FAIL",
        "A human reviewer failed at least one required Word visual or behavior check.",
      );
    } else if (humanResults.includes("BLOCKED")) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_WORD_HUMAN_REVIEW_BLOCKED",
        "BLOCKED",
        "At least one required Word visual or behavior check remains blocked.",
      );
    }
  }
  if (
    manifestByKey.size !== evidenceKeys.size ||
    [...manifestByKey.keys()].some((key) => !evidenceKeys.has(key))
  ) {
    addIssue(
      input.issues,
      "TT_HUMAN_GATE_WORD_DOCUMENT_SET_MISMATCH",
      "FAIL",
      "The Word evidence does not cover the complete package document set exactly once.",
    );
  }
}

function validatePhysicianEvidence(input: {
  readonly expectedSourceCommit: string;
  readonly manifestBytes: Uint8Array;
  readonly decisionBytes: Uint8Array;
  readonly issues: HumanGateValidationIssue[];
}): void {
  try {
    const manifest = PhysicianIntentManifestSchema.parse(
      parseJsonBytes(input.manifestBytes, "TT_HUMAN_GATE_PHYSICIAN_MANIFEST"),
    );
    if (manifest.sourceCommit !== input.expectedSourceCommit) {
      throw new Error("TT_HUMAN_GATE_PHYSICIAN_SOURCE_MISMATCH");
    }
    const fieldIds = new Set(manifest.fields.map((field) => field.fieldId));
    const references = new Set(
      manifest.fields.map((field) => field.referenceNumber),
    );
    if (
      manifest.fields.length !== WM_IOV_PLACEHOLDER_COUNT ||
      fieldIds.size !== WM_IOV_PLACEHOLDER_COUNT ||
      references.size !== WM_IOV_PLACEHOLDER_COUNT ||
      Array.from(
        { length: WM_IOV_PLACEHOLDER_COUNT },
        (_, index) => `P-0${index + 1}`,
      ).some(
        (reference) =>
          !references.has(reference as `P-0${1 | 2 | 3 | 4 | 5 | 6 | 7}`),
      )
    ) {
      throw new Error("TT_HUMAN_GATE_PHYSICIAN_FIELD_SET_MISMATCH");
    }
    const validation = validatePhysicianIntentDecisionFile({
      manifest,
      decisionFile: parseJsonBytes(
        input.decisionBytes,
        "TT_HUMAN_GATE_PHYSICIAN_DECISION",
      ),
    });
    if (
      validation.decisionFile.payload.sourceCommit !==
      input.expectedSourceCommit
    ) {
      throw new Error("TT_HUMAN_GATE_PHYSICIAN_SOURCE_MISMATCH");
    }
    if (validation.status === "BLOCKED") {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_PHYSICIAN_UNRESOLVED",
        "BLOCKED",
        "One or more physician placeholder decisions remain explicitly unresolved.",
      );
    }
  } catch (error) {
    addIssue(
      input.issues,
      errorCode(error, "TT_HUMAN_GATE_PHYSICIAN_EVIDENCE_INVALID"),
      "FAIL",
      "Physician intent evidence is malformed, altered, incomplete, stale, or not from a licensed physician.",
    );
  }
}

function validateMediaEvidence(input: {
  readonly expectedSourceCommit: string;
  readonly bytes: Uint8Array;
  readonly issues: HumanGateValidationIssue[];
}): void {
  try {
    const evidence = validateMediaReviewEvidenceFile({
      expectedSourceCommit: input.expectedSourceCommit,
      evidenceFile: parseJsonBytes(input.bytes, "TT_HUMAN_GATE_MEDIA_REVIEW"),
    });
    const payload = evidence.payload;
    const checklist = payload.checklist;
    const unsafe =
      !checklist.reusablePracticeLogoOrStaticAsset ||
      checklist.containsPatientInformation ||
      checklist.containsPatientOrPersonNamesOrIdentifiers ||
      checklist.containsPersonPhotographs ||
      checklist.containsBarcodesOrMachineReadableIdentifiers ||
      checklist.containsHiddenOrUnreviewedMetadata ||
      !checklist.organizationOwnsOrMayUseAsset ||
      payload.assetMetadata.privacyScanResult === "rejected";
    if (
      unsafe ||
      payload.recommendation === "recommend_authenticated_rejection"
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_MEDIA_REJECTED_OR_UNSAFE",
        "FAIL",
        "The practice administrator rejected the asset or recorded an unsafe media condition.",
      );
      return;
    }
    if (
      payload.recommendation !== "recommend_authenticated_approval" ||
      payload.assetMetadata.privacyScanResult !== "clear" ||
      payload.retentionAndVersion.currentAuthenticatedState !== "approved" ||
      payload.retentionAndVersion.retentionPolicyStatus !== "confirmed"
    ) {
      addIssue(
        input.issues,
        "TT_HUMAN_GATE_MEDIA_REVIEW_INCOMPLETE",
        "BLOCKED",
        "Media review is deferred, unauthenticated, revoked, or still missing required privacy/retention evidence.",
      );
    }
  } catch (error) {
    addIssue(
      input.issues,
      errorCode(error, "TT_HUMAN_GATE_MEDIA_EVIDENCE_INVALID"),
      "FAIL",
      "Media review evidence is malformed, altered, stale, or not from an authorized practice administrator.",
    );
  }
}

/**
 * Validates returned human evidence without importing or mutating anything.
 * A PASS means only that the offline evidence is complete and internally
 * consistent; the report is permanently marked as non-authorizing.
 */
export async function validateReturnedHumanGateEvidence(
  input: ValidateReturnedHumanGateEvidenceInput,
): Promise<HumanGateValidationReport> {
  const issues: HumanGateValidationIssue[] = [];
  if (!/^[a-f0-9]{40}$/u.test(input.expectedSourceCommit)) {
    addIssue(
      issues,
      "TT_HUMAN_GATE_EXPECTED_SOURCE_INVALID",
      "FAIL",
      "The expected source commit must be a full lowercase Git SHA.",
    );
  }
  const checkedAtIso = input.checkedAtIso ?? new Date().toISOString();
  if (Number.isNaN(Date.parse(checkedAtIso))) {
    addIssue(
      issues,
      "TT_HUMAN_GATE_CHECKED_AT_INVALID",
      "FAIL",
      "The validation timestamp is invalid.",
    );
  }

  await validateWordEvidence({
    bytes: Buffer.from(input.wordEvidenceZip),
    originalCiPackageBytes: Buffer.from(input.originalCiPackageZip),
    expectedOriginalCiPackageZipSha256:
      input.expectedOriginalCiPackageZipSha256,
    expectedSourceCommit: input.expectedSourceCommit,
    expectedZipSha256: input.expectedWordEvidenceZipSha256,
    officeArtifactVerifier: input.officeArtifactVerifier,
    trustedOpenXmlValidator: input.trustedOpenXmlValidator,
    issues,
  });
  validatePhysicianEvidence({
    expectedSourceCommit: input.expectedSourceCommit,
    manifestBytes: input.physicianManifestJson,
    decisionBytes: input.physicianDecisionJson,
    issues,
  });
  validateMediaEvidence({
    expectedSourceCommit: input.expectedSourceCommit,
    bytes: input.mediaReviewJson,
    issues,
  });

  return {
    contractVersion: "template-twin-human-release-gate-validation/1.0.0",
    sourceCommit: input.expectedSourceCommit,
    status: statusFromIssues(issues),
    authorizesClinicalOrProductionAction: false,
    inputs: {
      originalCiPackageZipSha256: sha256(input.originalCiPackageZip),
      wordEvidenceZipSha256: sha256(input.wordEvidenceZip),
      physicianDecisionSha256: sha256(input.physicianDecisionJson),
      mediaReviewSha256: sha256(input.mediaReviewJson),
    },
    issues: issues.sort((left, right) => left.code.localeCompare(right.code)),
    checkedAtIso,
  };
}
