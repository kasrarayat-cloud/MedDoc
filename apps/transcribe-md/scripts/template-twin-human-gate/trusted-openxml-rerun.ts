import { execFile, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  copyFile,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import {
  WORD_OPENXML_VALIDATOR_NAME,
  WORD_OPENXML_VALIDATOR_SDK_VERSION,
} from "../../src/lib/template-twin/human-release-gate/contracts";
import type {
  TrustedOpenXmlValidation,
  TrustedOpenXmlValidator,
} from "../../src/lib/template-twin/human-release-gate/evidence-validator";

const execFileAsync = promisify(execFile);
const DOTNET_IMAGE =
  "mcr.microsoft.com/dotnet/sdk@sha256:aabe48e2f28d3a10bed9cfb7beb8afc7ad4234578c0fdb11f03413b69941faea";
const VALIDATOR_SOURCE_FILES = Object.freeze([
  "OpenXmlValidator.csproj",
  "Program.cs",
  "packages.lock.json",
]);

interface OpenXmlReportResult {
  readonly file?: unknown;
  readonly sha256?: unknown;
  readonly sizeBytes?: unknown;
  readonly opened?: unknown;
  readonly valid?: unknown;
  readonly errorCount?: unknown;
  readonly errors?: unknown;
}

interface OpenXmlReport {
  readonly tool?: unknown;
  readonly sdkVersion?: unknown;
  readonly validatorExecutableSha256?: unknown;
  readonly targetFileFormat?: unknown;
  readonly sourceCommit?: unknown;
  readonly results?: unknown;
}

export interface TrustedOpenXmlValidatorHandle {
  readonly validate: TrustedOpenXmlValidator;
  readonly dispose: () => Promise<void>;
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

function assertTrustedSource(root: string, expectedSourceCommit: string): void {
  if (!/^[a-f0-9]{40}$/u.test(expectedSourceCommit)) {
    throw new Error("TT_HUMAN_GATE_TRUSTED_OPENXML_SOURCE_INVALID");
  }
  const head = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
  const status = execFileSync(
    "git",
    ["status", "--porcelain=v1", "--untracked-files=all"],
    {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    },
  ).trim();
  if (head !== expectedSourceCommit || status.length > 0) {
    throw new Error("TT_HUMAN_GATE_TRUSTED_OPENXML_SOURCE_MISMATCH");
  }
}

async function runDocker(
  args: readonly string[],
  options: { readonly acceptSchemaFailure?: boolean } = {},
): Promise<number> {
  try {
    await execFileAsync("docker", [...args], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
      timeout: 10 * 60 * 1_000,
    });
    return 0;
  } catch (error) {
    const exitCode =
      error && typeof error === "object" && "code" in error
        ? (error as { code: unknown }).code
        : null;
    if (options.acceptSchemaFailure && exitCode === 1) return 1;
    throw new Error("TT_HUMAN_GATE_TRUSTED_OPENXML_DOCKER_FAILED", {
      cause: error,
    });
  }
}

/**
 * Builds the pinned validator from the clean exact-head source checkout, then
 * reruns it with networking disabled against the exact returned DOCX bytes.
 * The executable shipped to the desktop reviewer is never executed or used as
 * a trust source by this verifier.
 */
export function createTrustedOpenXmlValidator(input: {
  readonly expectedSourceCommit: string;
}): TrustedOpenXmlValidatorHandle {
  const root = repositoryRoot();
  assertTrustedSource(root, input.expectedSourceCommit);
  let buildPromise: Promise<{
    readonly root: string;
    readonly executable: string;
    readonly executableSha256: string;
  }> | null = null;
  let runOrdinal = 0;

  const build = async () => {
    const buildRoot = await mkdtemp(
      path.join(os.tmpdir(), "template-twin-trusted-openxml-"),
    );
    const sourceRoot = path.join(
      root,
      "apps/transcribe-md/scripts/template-twin-human-gate/openxml-validator",
    );
    try {
      for (const filename of VALIDATOR_SOURCE_FILES) {
        await copyFile(
          path.join(sourceRoot, filename),
          path.join(buildRoot, filename),
        );
      }
      await runDocker([
        "run",
        "--rm",
        "--network",
        "bridge",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        `${process.getuid?.() ?? 1000}:${process.getgid?.() ?? 1000}`,
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=1g",
        "-e",
        "DOTNET_CLI_HOME=/tmp/dotnet-cli",
        "-e",
        "NUGET_PACKAGES=/tmp/nuget",
        "-v",
        `${buildRoot}:/src:rw`,
        "-w",
        "/src",
        DOTNET_IMAGE,
        "sh",
        "-c",
        "dotnet restore --locked-mode && dotnet publish --no-restore -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o /src/publish-linux",
      ]);
      const executable = path.join(
        buildRoot,
        "publish-linux",
        "OpenXmlValidator",
      );
      const metadata = await lstat(executable);
      if (
        !metadata.isFile() ||
        metadata.isSymbolicLink() ||
        metadata.size <= 0
      ) {
        throw new Error("TT_HUMAN_GATE_TRUSTED_OPENXML_BUILD_INVALID");
      }
      return {
        root: buildRoot,
        executable,
        executableSha256: sha256(await readFile(executable)),
      };
    } catch (error) {
      await rm(buildRoot, { recursive: true, force: true });
      throw error;
    }
  };

  const validate: TrustedOpenXmlValidator = async (
    validationInput,
  ): Promise<TrustedOpenXmlValidation> => {
    assertTrustedSource(root, input.expectedSourceCommit);
    if (
      validationInput.expectedSourceCommit !== input.expectedSourceCommit ||
      !/^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.docx$/u.test(
        validationInput.documentFilename,
      ) ||
      validationInput.documentBytes.byteLength <= 0
    ) {
      throw new Error("TT_HUMAN_GATE_TRUSTED_OPENXML_INPUT_INVALID");
    }
    buildPromise ??= build();
    const built = await buildPromise;
    runOrdinal += 1;
    const runRoot = path.join(
      built.root,
      `run-${runOrdinal.toString().padStart(4, "0")}`,
    );
    const inputRoot = path.join(runRoot, "input");
    const outputRoot = path.join(runRoot, "output");
    await mkdir(inputRoot, { recursive: true });
    await mkdir(outputRoot, { recursive: true });
    const documentPath = path.join(inputRoot, validationInput.documentFilename);
    const reportPath = path.join(outputRoot, "report.json");
    await writeFile(documentPath, validationInput.documentBytes, {
      flag: "wx",
    });
    const exitCode = await runDocker(
      [
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
        `OPENXML_TARGET=${validationInput.targetFileFormat}`,
        "-e",
        `QA_SOURCE_COMMIT=${input.expectedSourceCommit}`,
        "-e",
        `QA_GENERATED_AT=${new Date().toISOString()}`,
        "-v",
        `${path.dirname(built.executable)}:/validator:ro`,
        "-v",
        `${inputRoot}:/input:ro`,
        "-v",
        `${outputRoot}:/out:rw`,
        "-w",
        "/out",
        "--entrypoint",
        "/validator/OpenXmlValidator",
        DOTNET_IMAGE,
        "/out/report.json",
        `/input/${validationInput.documentFilename}`,
      ],
      { acceptSchemaFailure: true },
    );
    const report = JSON.parse(
      await readFile(reportPath, "utf8"),
    ) as OpenXmlReport;
    const results = Array.isArray(report.results)
      ? (report.results as OpenXmlReportResult[])
      : [];
    const result = results.length === 1 ? results[0]! : {};
    const documentSha256 = sha256(validationInput.documentBytes);
    const documentSizeBytes = validationInput.documentBytes.byteLength;
    const reportIdentityValid = Boolean(
      report.tool === WORD_OPENXML_VALIDATOR_NAME &&
      report.sdkVersion === WORD_OPENXML_VALIDATOR_SDK_VERSION &&
      report.validatorExecutableSha256 === built.executableSha256 &&
      report.targetFileFormat === validationInput.targetFileFormat &&
      report.sourceCommit === input.expectedSourceCommit &&
      result.file === validationInput.documentFilename &&
      result.sha256 === documentSha256 &&
      result.sizeBytes === documentSizeBytes &&
      typeof result.errorCount === "number" &&
      Number.isSafeInteger(result.errorCount) &&
      Array.isArray(result.errors),
    );
    const errorCount =
      typeof result.errorCount === "number" &&
      Number.isSafeInteger(result.errorCount) &&
      result.errorCount >= 0
        ? result.errorCount
        : 1;
    const valid = Boolean(
      reportIdentityValid &&
      exitCode === 0 &&
      result.opened === true &&
      result.valid === true &&
      errorCount === 0 &&
      Array.isArray(result.errors) &&
      result.errors.length === 0,
    );
    return {
      contractVersion: "template-twin-trusted-openxml-rerun/1.0.0",
      tool: WORD_OPENXML_VALIDATOR_NAME,
      sdkVersion: WORD_OPENXML_VALIDATOR_SDK_VERSION,
      validatorSourceCommit: input.expectedSourceCommit,
      validatorExecutableSha256: built.executableSha256,
      returnedExecutableUsed: false,
      networkModeDuringValidation: "none",
      targetFileFormat: validationInput.targetFileFormat,
      documentFilename: validationInput.documentFilename,
      documentSha256,
      documentSizeBytes,
      valid,
      errorCount,
    };
  };

  return {
    validate,
    dispose: async () => {
      if (!buildPromise) return;
      const built = await buildPromise.catch(() => null);
      if (
        built?.root.startsWith(
          path.join(os.tmpdir(), "template-twin-trusted-openxml-"),
        )
      ) {
        await rm(built.root, { recursive: true, force: true });
      }
    },
  };
}
