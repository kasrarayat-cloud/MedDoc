import { execFile, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import {
  POST_LIBREOFFICE_ARTIFACTS,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
  POST_LIBREOFFICE_TARGETS,
} from "../../src/lib/note-template-docx/office-libreoffice-reviewed-registry";
import {
  buildPostLibreOfficeEvidenceManifest,
  POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256,
  POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
  type PostLibreOfficeRawReportInput,
  type PostLibreOfficeSavedArtifactInput,
} from "../../src/lib/note-template-docx/office-post-libreoffice-evidence";

const execFileAsync = promisify(execFile);
const DOTNET_IMAGE =
  "mcr.microsoft.com/dotnet/sdk@sha256:aabe48e2f28d3a10bed9cfb7beb8afc7ad4234578c0fdb11f03413b69941faea";

function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function option(name: string): string {
  const index = process.argv.indexOf(`--${name}`);
  invariant(index >= 0 && process.argv[index + 1], `Missing --${name}.`);
  return process.argv[index + 1];
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function repositoryRoot(): string {
  return execFileSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: process.cwd(),
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

async function runValidator(args: readonly string[]): Promise<void> {
  try {
    await execFileAsync("docker", [...args], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
      timeout: 10 * 60 * 1_000,
    });
  } catch (error) {
    const exitCode =
      error && typeof error === "object" && "code" in error
        ? (error as { code: unknown }).code
        : null;
    // The pinned validator returns one when it opens a package and reports
    // schema diagnostics. The closed classifier below must still verify every
    // exact diagnostic before that result can be packaged as Word-pending.
    if (exitCode === 1) return;
    throw new Error("POST_LIBREOFFICE_VALIDATOR_EXECUTION_FAILED", {
      cause: error,
    });
  }
}

async function main(): Promise<void> {
  const inputRoot = option("input-root");
  const sourceCommit = option("source-commit");
  const generatedAtIso = option("generated-at");
  invariant(
    inputRoot === `/tmp/template-twin-human-gate-${sourceCommit.slice(0, 12)}`,
    "Input must be the exact dedicated human-gate root.",
  );
  invariant(
    /^[a-f0-9]{40}$/u.test(sourceCommit),
    "A full lowercase source commit is required.",
  );
  invariant(
    !Number.isNaN(Date.parse(generatedAtIso)),
    "A deterministic generated-at timestamp is required.",
  );
  const root = repositoryRoot();
  invariant(
    execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: root,
      encoding: "utf8",
    }).trim() === sourceCommit,
    "Checked-out repository does not match the evidence source commit.",
  );
  invariant(
    execFileSync("git", ["status", "--porcelain=v1", "--untracked-files=all"], {
      cwd: root,
      encoding: "utf8",
    }).trim().length === 0,
    "Post-LibreOffice evidence requires a clean exact-head checkout.",
  );

  const buildRoot = path.join(inputRoot, "openxml-build");
  const linuxExecutable = path.join(
    buildRoot,
    "publish-linux",
    "OpenXmlValidator",
  );
  const windowsExecutable = path.join(
    buildRoot,
    "publish-windows",
    "OpenXmlValidator.exe",
  );
  const linuxExecutableSha256 = sha256(await readFile(linuxExecutable));
  const windowsExecutableSha256 = sha256(await readFile(windowsExecutable));
  invariant(
    linuxExecutableSha256 === POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256 &&
      windowsExecutableSha256 ===
        POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
    "POST_LIBREOFFICE_VALIDATOR_IDENTITY_DRIFT",
  );

  const officeRoot = path.join(inputRoot, "office-evidence");
  const outputRoot = path.join(officeRoot, "openxml-post-libreoffice");
  await rm(outputRoot, { recursive: true, force: true });
  await mkdir(outputRoot, { recursive: true });

  const savedArtifacts: PostLibreOfficeSavedArtifactInput[] = [];
  const containerDocuments: string[] = [];
  for (const artifact of POST_LIBREOFFICE_ARTIFACTS) {
    const hostPath = path.join(
      officeRoot,
      "cases",
      artifact.caseId,
      "saved",
      artifact.filename,
    );
    const bytes = await readFile(hostPath);
    const observed = {
      caseId: artifact.caseId,
      filename: artifact.filename,
      sha256: sha256(bytes),
      sizeBytes: bytes.length,
    };
    invariant(
      /^[a-f0-9]{64}$/u.test(observed.sha256) && observed.sizeBytes > 0,
      `POST_LIBREOFFICE_ARTIFACT_IDENTITY_DRIFT:${artifact.caseId}`,
    );
    savedArtifacts.push(observed);
    containerDocuments.push(
      `/cases/${artifact.caseId}/saved/${artifact.filename}`,
    );
  }

  const rawReports: PostLibreOfficeRawReportInput[] = [];
  for (const target of POST_LIBREOFFICE_TARGETS) {
    const filename = `post-libreoffice-${target}.json`;
    await runValidator([
      "run",
      "--rm",
      "--network",
      "none",
      "--read-only",
      "--cap-drop",
      "ALL",
      "--security-opt",
      "no-new-privileges",
      "--user",
      `${process.getuid?.() ?? 1000}:${process.getgid?.() ?? 1000}`,
      "--memory",
      "768m",
      "--cpus",
      "2",
      "--pids-limit",
      "128",
      "--tmpfs",
      "/tmp:rw,noexec,nosuid,size=128m",
      "-e",
      `OPENXML_TARGET=${target}`,
      "-e",
      `QA_SOURCE_COMMIT=${sourceCommit}`,
      "-e",
      `QA_GENERATED_AT=${generatedAtIso}`,
      "-v",
      `${path.dirname(linuxExecutable)}:/validator:ro`,
      "-v",
      `${path.join(officeRoot, "cases")}:/cases:ro`,
      "-v",
      `${outputRoot}:/out:rw`,
      "-w",
      "/out",
      "--entrypoint",
      "/validator/OpenXmlValidator",
      DOTNET_IMAGE,
      `/out/${filename}`,
      ...containerDocuments,
    ]);
    rawReports.push({
      relativePath: filename,
      bytes: await readFile(path.join(outputRoot, filename)),
    });
  }

  const manifest = buildPostLibreOfficeEvidenceManifest({
    sourceCommit,
    generatedAtIso,
    validatorExecutableSha256: linuxExecutableSha256,
    windowsValidatorExecutableSha256: windowsExecutableSha256,
    libreOfficeResults: {
      relativePath: "libreoffice-results.json",
      bytes: await readFile(path.join(officeRoot, "libreoffice-results.json")),
    },
    rawReports,
    savedArtifacts,
  });
  const manifestPath = path.join(outputRoot, "canonical-manifest.json");
  await writeFile(
    manifestPath,
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
  await writeFile(
    path.join(outputRoot, "observation-registry.json"),
    `${JSON.stringify(
      {
        ...POST_LIBREOFFICE_OBSERVATION_REGISTRY,
        registrySha256: POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  const evidenceFiles = [
    ...rawReports.map((report) => report.relativePath),
    "canonical-manifest.json",
    "observation-registry.json",
  ].sort();
  const sums = await Promise.all(
    evidenceFiles.map(
      async (filename) =>
        `${sha256(await readFile(path.join(outputRoot, filename)))}  ${filename}`,
    ),
  );
  await writeFile(
    path.join(outputRoot, "SHA256SUMS.txt"),
    `${sums.join("\n")}\n`,
    "ascii",
  );
  process.stdout.write(
    `${JSON.stringify({
      sourceCommit,
      savedArtifacts: manifest.totals.savedArtifacts,
      physicalFindings: manifest.totals.physicalFindings,
      targetObservations: manifest.totals.targetObservations,
      schemaStatus: manifest.schemaStatus,
      independentReviewStatus:
        manifest.reviewProvenance.independentReviewStatus,
      desktopWordStatus: "PENDING",
      evidenceSha256: manifest.evidenceSha256,
    })}\n`,
  );
}

void main();
