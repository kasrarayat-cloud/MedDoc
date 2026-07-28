import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import {
  readOfficeSavedDocxFieldsQa,
  type OfficeExpectedValueManifest,
} from "../../src/lib/note-template-docx/office-docx-byte-readback";
import {
  buildOfficeVisibleStaticManifestFromDocxBytes,
  compareOfficeVisibleStaticManifests,
  inspectOfficeDocxSecurityQa,
  OFFICE_PINNED_IMAGE,
} from "../../src/lib/note-template-docx/office-roundtrip-qa";

const TIMEOUT_MS = 180_000;
const POPPLER_IMAGE =
  "elswork/poppler-utils@sha256:c83008ec08ac1a67d5f1ff0a8a1d867e8165262efbbfbaef65ea6a7755161754";

interface CommandResult {
  readonly command: readonly string[];
  readonly exitCode: number;
  readonly timedOut: boolean;
  readonly stdout: string;
  readonly stderr: string;
  readonly warningLines: readonly string[];
}

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

async function run(
  command: string,
  args: readonly string[],
): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.once("error", reject);
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, TIMEOUT_MS);
    child.once("close", (code) => {
      clearTimeout(timer);
      resolve({
        command: [command, ...args],
        exitCode: code ?? 1,
        timedOut,
        stdout,
        stderr,
        warningLines: `${stdout}\n${stderr}`
          .split(/\r?\n/u)
          .map((line) => line.trim())
          .filter((line) =>
            /(?:warn|error|repair|corrupt|unsupported|fail)/iu.test(line),
          ),
      });
    });
  });
}

function containerPath(
  hostPath: string,
  inputRoot: string,
  outputRoot: string,
): string {
  if (
    hostPath === outputRoot ||
    hostPath.startsWith(`${outputRoot}${path.sep}`)
  ) {
    return hostPath.replace(outputRoot, "/gate-output");
  }
  if (
    hostPath === inputRoot ||
    hostPath.startsWith(`${inputRoot}${path.sep}`)
  ) {
    return hostPath.replace(inputRoot, "/gate-input");
  }
  throw new Error(`Path is outside isolated LibreOffice mounts: ${hostPath}`);
}

function libreOfficeArgs(
  inputRoot: string,
  outputRoot: string,
  profile: string,
  args: readonly string[],
): string[] {
  return [
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
    `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`,
    "--memory",
    "1g",
    "--cpus",
    "2",
    "--pids-limit",
    "256",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=512m",
    "-e",
    "HOME=/tmp/lo-home",
    "-v",
    `${inputRoot}:/gate-input:ro`,
    "-v",
    `${outputRoot}:/gate-output:rw`,
    "-w",
    "/gate-output",
    "--entrypoint",
    "/usr/bin/libreoffice",
    OFFICE_PINNED_IMAGE,
    `-env:UserInstallation=file:///gate-output/profiles/${profile}`,
    "--headless",
    "--nologo",
    "--nodefault",
    "--nolockcheck",
    "--nofirststartwizard",
    ...args,
  ];
}

async function convert(
  inputRoot: string,
  outputRoot: string,
  input: string,
  outDir: string,
  profile: string,
  format: string,
): Promise<CommandResult> {
  return run(
    "docker",
    libreOfficeArgs(inputRoot, outputRoot, profile, [
      "--convert-to",
      format,
      "--outdir",
      containerPath(outDir, inputRoot, outputRoot),
      containerPath(input, inputRoot, outputRoot),
    ]),
  );
}

function popplerArgs(
  entrypoint: "pdfinfo" | "pdftoppm" | "pdftotext",
  inputFile: string,
  outputRoot: string | null,
  args: readonly string[],
): string[] {
  return [
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
    `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`,
    "--memory",
    "512m",
    "--cpus",
    "1",
    "--pids-limit",
    "64",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=64m",
    "-e",
    "HOME=/tmp",
    "-v",
    `${inputFile}:/input.pdf:ro`,
    ...(outputRoot ? ["-v", `${outputRoot}:/output:rw`] : []),
    "--entrypoint",
    entrypoint,
    POPPLER_IMAGE,
    ...args,
  ];
}

async function pdfEvidence(
  file: string,
  imageRoot: string,
): Promise<{
  pageCount: number;
  pageImageSha256: string[];
  visibleText: { path: string; sha256: string; sizeBytes: number };
}> {
  const info = await run(
    "docker",
    popplerArgs("pdfinfo", file, null, ["/input.pdf"]),
  );
  invariant(
    info.exitCode === 0 && !info.timedOut,
    `pdfinfo failed for ${path.basename(file)}.`,
  );
  const pageMatch = info.stdout.match(/^Pages:\s+(\d+)$/mu);
  invariant(
    pageMatch,
    `PDF page count is unavailable for ${path.basename(file)}.`,
  );
  await mkdir(imageRoot, { recursive: true });
  const render = await run(
    "docker",
    popplerArgs("pdftoppm", file, imageRoot, [
      "-r",
      "144",
      "-png",
      "/input.pdf",
      "/output/page",
    ]),
  );
  invariant(
    render.exitCode === 0 && !render.timedOut,
    `PDF rasterization failed for ${path.basename(file)}.`,
  );
  const visibleTextPath = path.join(imageRoot, "visible-text.txt");
  const extractText = await run(
    "docker",
    popplerArgs("pdftotext", file, imageRoot, [
      "/input.pdf",
      "/output/visible-text.txt",
    ]),
  );
  invariant(
    extractText.exitCode === 0 &&
      !extractText.timedOut &&
      extractText.warningLines.length === 0,
    `PDF visible-text extraction failed for ${path.basename(file)}.`,
  );
  const images = (await readdir(imageRoot))
    .filter((name) => name.endsWith(".png"))
    .sort();
  invariant(
    images.length === Number(pageMatch[1]),
    "Rasterized page count mismatch.",
  );
  const visibleTextBytes = await readFile(visibleTextPath);
  return {
    pageCount: Number(pageMatch[1]),
    pageImageSha256: await Promise.all(
      images.map(async (name) =>
        sha256(await readFile(path.join(imageRoot, name))),
      ),
    ),
    visibleText: {
      path: visibleTextPath,
      sha256: sha256(visibleTextBytes),
      sizeBytes: visibleTextBytes.length,
    },
  };
}

async function main(): Promise<void> {
  const inputRoot = option("input-root");
  const sourceCommit = option("source-commit");
  const generatedAtIso = option("generated-at");
  invariant(
    inputRoot.startsWith("/tmp/template-twin-human-gate-"),
    "Input must use the dedicated /tmp namespace.",
  );
  invariant(
    /^[a-f0-9]{40}$/u.test(sourceCommit),
    "A full lowercase source commit is required.",
  );
  invariant(
    !Number.isNaN(Date.parse(generatedAtIso)),
    "A deterministic generated-at timestamp is required.",
  );
  const corpusRoot = path.join(inputRoot, "corpus");
  const outputRoot = path.join(inputRoot, "office-evidence");
  // This runner owns only these paths. Open XML evidence is a sibling owned by
  // a separate rerunnable harness and must survive LibreOffice reruns.
  await rm(path.join(outputRoot, "cases"), { recursive: true, force: true });
  await rm(path.join(outputRoot, "profiles"), { recursive: true, force: true });
  await rm(path.join(outputRoot, "libreoffice-results.json"), { force: true });
  await mkdir(path.join(outputRoot, "profiles"), { recursive: true });
  const manifest = JSON.parse(
    await readFile(path.join(corpusRoot, "corpus-manifest.json"), "utf8"),
  ) as {
    sourceCommit: string;
    syntheticOnly: boolean;
    cases: Array<{
      id: string;
      status: string;
      sourcePath: string;
      outputPath: string | null;
      minimumExpectedPages: number;
    }>;
  };
  invariant(
    manifest.sourceCommit === sourceCommit && manifest.syntheticOnly,
    "Corpus provenance mismatch.",
  );
  const version = await run("docker", [
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
    `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`,
    "--memory",
    "512m",
    "--cpus",
    "1",
    "--pids-limit",
    "64",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=64m",
    "-e",
    "HOME=/tmp",
    "--entrypoint",
    "/usr/bin/libreoffice",
    OFFICE_PINNED_IMAGE,
    "--version",
  ]);
  invariant(
    version.exitCode === 0 && !version.timedOut,
    "Pinned LibreOffice image is unavailable.",
  );
  const popplerVersion = await run("docker", [
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
    `${process.getuid?.() ?? 0}:${process.getgid?.() ?? 0}`,
    "--memory",
    "256m",
    "--cpus",
    "1",
    "--pids-limit",
    "32",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=32m",
    "-e",
    "HOME=/tmp",
    "--entrypoint",
    "pdfinfo",
    POPPLER_IMAGE,
    "-v",
  ]);
  invariant(
    popplerVersion.exitCode === 0 && !popplerVersion.timedOut,
    "Pinned Poppler image is unavailable.",
  );
  const results: Record<string, unknown>[] = [];
  const documentPages: Record<string, unknown>[] = [];
  for (const item of manifest.cases) {
    const caseRoot = path.join(outputRoot, "cases", item.id);
    const sourcePdfDir = path.join(caseRoot, "source-pdf");
    await mkdir(sourcePdfDir, { recursive: true });
    const sourcePdfCommand = await convert(
      inputRoot,
      outputRoot,
      item.sourcePath,
      sourcePdfDir,
      `${item.id}-source-pdf`,
      "pdf:writer_pdf_Export",
    );
    invariant(
      sourcePdfCommand.exitCode === 0 &&
        !sourcePdfCommand.timedOut &&
        sourcePdfCommand.warningLines.length === 0,
      `${item.id}: LibreOffice source PDF conversion failed or warned.`,
    );
    const generatedSourcePdf = path.join(
      sourcePdfDir,
      `${path.parse(item.sourcePath).name}.pdf`,
    );
    const sourcePdf = path.join(sourcePdfDir, `${item.id}.source.pdf`);
    await rename(generatedSourcePdf, sourcePdf);
    const sourceVisual = await pdfEvidence(
      sourcePdf,
      path.join(caseRoot, "source-pages"),
    );
    const sourceBytes = await readFile(item.sourcePath);
    const sourcePdfBytes = await readFile(sourcePdf);
    documentPages.push({
      caseId: item.id,
      documentRole: "source",
      documentSha256: sha256(sourceBytes),
      pageCount: sourceVisual.pageCount,
      pdf: {
        path: sourcePdf,
        sha256: sha256(sourcePdfBytes),
        sizeBytes: sourcePdfBytes.length,
      },
      visibleText: sourceVisual.visibleText,
      command: sourcePdfCommand,
    });
  }
  for (const item of manifest.cases.filter(
    (candidate) => candidate.status === "rendered_verified",
  )) {
    invariant(
      item.outputPath,
      `${item.id}: verified corpus case has no output.`,
    );
    const caseRoot = path.join(outputRoot, "cases", item.id);
    const savedDir = path.join(caseRoot, "saved");
    const rendererPdfDir = path.join(caseRoot, "renderer-pdf");
    const roundtripPdfDir = path.join(caseRoot, "roundtrip-pdf");
    await Promise.all(
      [savedDir, rendererPdfDir, roundtripPdfDir].map((directory) =>
        mkdir(directory, { recursive: true }),
      ),
    );
    const savedCommand = await convert(
      inputRoot,
      outputRoot,
      item.outputPath,
      savedDir,
      `${item.id}-save`,
      "docx:Office Open XML Text",
    );
    const generatedSaved = path.join(savedDir, path.basename(item.outputPath));
    const savedDocx = path.join(savedDir, `${item.id}.libreoffice-saved.docx`);
    if (savedCommand.exitCode === 0) await rename(generatedSaved, savedDocx);
    const rendererPdfCommand = await convert(
      inputRoot,
      outputRoot,
      item.outputPath,
      rendererPdfDir,
      `${item.id}-renderer-pdf`,
      "pdf:writer_pdf_Export",
    );
    const generatedRendererPdf = path.join(
      rendererPdfDir,
      `${path.parse(item.outputPath).name}.pdf`,
    );
    const rendererPdf = path.join(rendererPdfDir, `${item.id}.renderer.pdf`);
    if (rendererPdfCommand.exitCode === 0)
      await rename(generatedRendererPdf, rendererPdf);
    const roundtripPdfCommand = await convert(
      inputRoot,
      outputRoot,
      savedDocx,
      roundtripPdfDir,
      `${item.id}-roundtrip-pdf`,
      "pdf:writer_pdf_Export",
    );
    const generatedRoundtripPdf = path.join(
      roundtripPdfDir,
      `${path.parse(savedDocx).name}.pdf`,
    );
    const roundtripPdf = path.join(roundtripPdfDir, `${item.id}.roundtrip.pdf`);
    if (roundtripPdfCommand.exitCode === 0)
      await rename(generatedRoundtripPdf, roundtripPdf);
    const commands = [savedCommand, rendererPdfCommand, roundtripPdfCommand];
    invariant(
      commands.every((command) => command.exitCode === 0 && !command.timedOut),
      `${item.id}: LibreOffice conversion failed.`,
    );
    invariant(
      commands.every((command) => command.warningLines.length === 0),
      `${item.id}: LibreOffice warning requires review.`,
    );

    const rendererBytes = await readFile(item.outputPath);
    const savedBytes = await readFile(savedDocx);
    const expected = JSON.parse(
      await readFile(
        path.join(corpusRoot, item.id, "office-expected-manifest.json"),
        "utf8",
      ),
    ) as OfficeExpectedValueManifest;
    const readback = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: savedBytes,
      expected,
    });
    const expectedById = new Map(
      expected.fields.map((field) => [field.fieldId, field]),
    );
    const semanticSurvival =
      readback.unexpectedBindingCount === 0 &&
      readback.ambiguousBindingCount === 0 &&
      readback.fields.length === expected.fields.length &&
      readback.fields.every((field) => {
        const baseline = expectedById.get(field.fieldId);
        return Boolean(
          baseline &&
          field.actualOccurrences === 1 &&
          field.actualValueSha256 === baseline.expectedValueSha256 &&
          field.actualControlStateSha256 ===
            baseline.expectedControlStateSha256,
        );
      });
    invariant(
      semanticSurvival,
      `${item.id}: post-LibreOffice field/control survival failed.`,
    );
    const rendererStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: rendererBytes,
      expected,
    });
    const savedStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: savedBytes,
      expected,
    });
    const staticComparison = compareOfficeVisibleStaticManifests(
      rendererStatic.manifest,
      savedStatic.manifest,
    );
    invariant(
      staticComparison.aggregateVisibleContentMatches,
      `${item.id}: visible static text changed.`,
    );
    const security = inspectOfficeDocxSecurityQa(savedBytes);
    invariant(
      security.status === "passed",
      `${item.id}: post-LibreOffice security inspection failed.`,
    );
    const rendererVisual = await pdfEvidence(
      rendererPdf,
      path.join(caseRoot, "renderer-pages"),
    );
    const roundtripVisual = await pdfEvidence(
      roundtripPdf,
      path.join(caseRoot, "roundtrip-pages"),
    );
    const visualPass =
      rendererVisual.pageCount === roundtripVisual.pageCount &&
      rendererVisual.pageCount >= item.minimumExpectedPages &&
      JSON.stringify(rendererVisual.pageImageSha256) ===
        JSON.stringify(roundtripVisual.pageImageSha256);
    invariant(
      visualPass,
      `${item.id}: LibreOffice PDF pixel comparison failed.`,
    );
    const rendererPdfBytes = await readFile(rendererPdf);
    documentPages.push({
      caseId: item.id,
      documentRole: "renderer_output",
      documentSha256: sha256(rendererBytes),
      pageCount: rendererVisual.pageCount,
      pdf: {
        path: rendererPdf,
        sha256: sha256(rendererPdfBytes),
        sizeBytes: rendererPdfBytes.length,
      },
      visibleText: rendererVisual.visibleText,
      command: rendererPdfCommand,
    });
    results.push({
      id: item.id,
      sourceCommit,
      commands,
      rendererOutput: {
        sha256: sha256(rendererBytes),
        sizeBytes: rendererBytes.length,
      },
      libreOfficeSaved: {
        sha256: sha256(savedBytes),
        sizeBytes: savedBytes.length,
      },
      semanticReadback: readback,
      semanticSurvival,
      staticComparison,
      staticCompatibility: {
        status: staticComparison.aggregateStructureMatches
          ? "normalized_equivalent"
          : "structural_normalization_recorded",
        normalizedVisibleStaticPreserved:
          staticComparison.aggregateVisibleContentMatches,
        exactStructurePreserved: staticComparison.aggregateStructureMatches,
        signingOrImportEligible: false,
      },
      security,
      visual: {
        status: "passed",
        renderer: rendererVisual,
        roundtrip: roundtripVisual,
      },
      pdfs: {
        renderer: {
          path: rendererPdf,
          sha256: sha256(await readFile(rendererPdf)),
          sizeBytes: (await readFile(rendererPdf)).length,
        },
        roundtrip: {
          path: roundtripPdf,
          sha256: sha256(await readFile(roundtripPdf)),
          sizeBytes: (await readFile(roundtripPdf)).length,
        },
      },
    });
  }
  const evidence = {
    contractVersion: "template-twin-human-gate-libreoffice-evidence/1.0.0",
    sourceCommit,
    generatedAtIso,
    syntheticOnly: true,
    networkMode: "none",
    image: OFFICE_PINNED_IMAGE,
    version,
    poppler: { image: POPPLER_IMAGE, version: popplerVersion },
    results,
    documentPages,
    overallStatus: "passed",
    microsoftWordStatus: "PENDING",
  };
  await writeFile(
    path.join(outputRoot, "libreoffice-results.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
    "utf8",
  );
  process.stdout.write(
    `${JSON.stringify({ version: version.stdout.trim(), cases: results.length, status: "passed" })}\n`,
  );
}

void main();
