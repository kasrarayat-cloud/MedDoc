import { lstat, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { validateReturnedHumanGateEvidence } from "../../src/lib/template-twin/human-release-gate/evidence-validator";
import { verifyReturnedOfficeArtifacts } from "./returned-office-artifact-verifier";
import { createTrustedOpenXmlValidator } from "./trusted-openxml-rerun";

const MAX_WORD_EVIDENCE_ZIP_BYTES = 256 * 1024 * 1024;
const MAX_JSON_BYTES = 8 * 1024 * 1024;

interface Options {
  readonly expectedSourceCommit: string;
  readonly originalCiPackageZip: string;
  readonly trustedOriginalCiPackageSha256: string;
  readonly wordEvidenceZip: string;
  readonly physicianManifest: string;
  readonly physicianDecision: string;
  readonly mediaReview: string;
  readonly output: string;
}

function parseOptions(argv: readonly string[]): Options {
  const allowed = new Set([
    "expected-source-commit",
    "original-ci-package-zip",
    "trusted-original-ci-package-sha256",
    "word-evidence-zip",
    "physician-manifest",
    "physician-decision",
    "media-review",
    "output",
  ]);
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || !value || values.has(key.slice(2))) {
      throw new Error("Expected unique --name value arguments.");
    }
    const name = key.slice(2);
    if (!allowed.has(name)) throw new Error(`Unknown option --${name}.`);
    values.set(name, value);
  }
  const required = (name: string): string => {
    const value = values.get(name);
    if (!value) throw new Error(`Missing --${name}.`);
    return value;
  };
  const output = path.resolve(required("output"));
  if (!(output === "/tmp" || output.startsWith("/tmp/"))) {
    throw new Error(
      "The non-production validation report must be written under /tmp.",
    );
  }
  return {
    expectedSourceCommit: required("expected-source-commit"),
    originalCiPackageZip: path.resolve(required("original-ci-package-zip")),
    trustedOriginalCiPackageSha256: required(
      "trusted-original-ci-package-sha256",
    ),
    wordEvidenceZip: path.resolve(required("word-evidence-zip")),
    physicianManifest: path.resolve(required("physician-manifest")),
    physicianDecision: path.resolve(required("physician-decision")),
    mediaReview: path.resolve(required("media-review")),
    output,
  };
}

async function boundedRead(
  file: string,
  maximumBytes: number,
): Promise<Buffer> {
  const metadata = await lstat(file);
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    metadata.size <= 0 ||
    metadata.size > maximumBytes
  ) {
    throw new Error(
      `Input is not a bounded regular file: ${path.basename(file)}`,
    );
  }
  return readFile(file);
}

async function adjacentZipSha256(zipFile: string): Promise<string | undefined> {
  const sidecar = `${zipFile}.sha256`;
  try {
    const metadata = await lstat(sidecar);
    if (
      !metadata.isFile() ||
      metadata.isSymbolicLink() ||
      metadata.size > 1_024
    ) {
      throw new Error(
        "Adjacent ZIP SHA-256 sidecar is not a bounded regular file.",
      );
    }
    const text = await readFile(sidecar, "utf8");
    const match = text
      .trim()
      .match(/^([a-f0-9]{64})  ([A-Za-z0-9._-]+\.zip)$/u);
    if (!match || match[2] !== path.basename(zipFile)) {
      throw new Error(
        "Adjacent ZIP SHA-256 sidecar has an invalid digest or filename.",
      );
    }
    return match[1];
  } catch (error) {
    // Absence is passed into the validator so callers still receive a
    // machine-readable FAIL report rather than an unclassified CLI crash.
    if (error instanceof Error && "code" in error && error.code === "ENOENT")
      return undefined;
    // Any present-but-malformed, unsafe, or unreadable sidecar is represented
    // by a non-digest sentinel. The validator classifies it as a hash mismatch
    // and still writes the required non-authorizing FAIL report.
    return "invalid-sidecar";
  }
}

async function main(): Promise<void> {
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "This evidence inspection command is disabled when NODE_ENV=production.",
    );
  }
  const options = parseOptions(process.argv.slice(2));
  const [
    originalCiPackageZip,
    wordEvidenceZip,
    physicianManifestJson,
    physicianDecisionJson,
    mediaReviewJson,
  ] = await Promise.all([
    boundedRead(options.originalCiPackageZip, MAX_WORD_EVIDENCE_ZIP_BYTES),
    boundedRead(options.wordEvidenceZip, MAX_WORD_EVIDENCE_ZIP_BYTES),
    boundedRead(options.physicianManifest, MAX_JSON_BYTES),
    boundedRead(options.physicianDecision, MAX_JSON_BYTES),
    boundedRead(options.mediaReview, MAX_JSON_BYTES),
  ]);
  const trustedOpenXml = createTrustedOpenXmlValidator({
    expectedSourceCommit: options.expectedSourceCommit,
  });
  let report: Awaited<ReturnType<typeof validateReturnedHumanGateEvidence>>;
  try {
    report = await validateReturnedHumanGateEvidence({
      expectedSourceCommit: options.expectedSourceCommit,
      originalCiPackageZip,
      expectedOriginalCiPackageZipSha256:
        options.trustedOriginalCiPackageSha256,
      wordEvidenceZip,
      expectedWordEvidenceZipSha256: await adjacentZipSha256(
        options.wordEvidenceZip,
      ),
      physicianManifestJson,
      physicianDecisionJson,
      mediaReviewJson,
      officeArtifactVerifier: verifyReturnedOfficeArtifacts,
      trustedOpenXmlValidator: trustedOpenXml.validate,
    });
  } finally {
    await trustedOpenXml.dispose();
  }
  await writeFile(options.output, `${JSON.stringify(report, null, 2)}\n`, {
    encoding: "utf8",
    flag: "wx",
  });
  process.stdout.write(
    `${report.status}: ${report.issues.length} issue(s). Report: ${options.output}\n`,
  );
  process.exitCode =
    report.status === "PASS" ? 0 : report.status === "BLOCKED" ? 3 : 2;
}

void main();
