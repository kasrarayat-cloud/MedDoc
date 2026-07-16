import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { compileTemplateDocx } from "../../src/lib/note-template-docx/compiler";
import {
  MEDIA_REVIEW_EVIDENCE_JSON_SCHEMA,
  PHYSICIAN_INTENT_DECISION_JSON_SCHEMA,
  buildWmIovPhysicianIntentManifest,
  renderMediaReviewWorksheetHtml,
  renderPhysicianIntentWorksheetHtml,
} from "../../src/lib/template-twin/human-gate";

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

async function writeJson(file: string, value: unknown): Promise<void> {
  await writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function main(): Promise<void> {
  const outputRoot = option("output-root");
  const sourceCommit = option("source-commit");
  const generatedAtIso = option("generated-at");
  invariant(
    outputRoot.startsWith("/tmp/template-twin-human-gate-"),
    "Output must use the dedicated /tmp namespace.",
  );
  invariant(
    /^[a-f0-9]{40}$/u.test(sourceCommit),
    "A full lowercase source commit is required.",
  );
  invariant(
    !Number.isNaN(Date.parse(generatedAtIso)),
    "A deterministic generated-at timestamp is required.",
  );
  const repositoryRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: process.cwd(),
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
  invariant(
    execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: repositoryRoot,
      encoding: "utf8",
    }).trim() === sourceCommit,
    "Checked-out repository does not match the requested source commit.",
  );

  // This file is read only to derive compiler-owned hashes and structural
  // references. Its bytes, labels, token text, media, and extracted contents
  // are never written to the packet or stdout.
  const source = await readFile(
    path.join(repositoryRoot, "WM IOV Template.docx"),
  );
  const ir = compileTemplateDocx(source);
  const manifest = buildWmIovPhysicianIntentManifest({
    ir,
    sourceCommit,
    sourceDocumentSha256: sha256(source),
    generatedAtIso,
  });
  invariant(
    manifest.fields.length === 7,
    "Expected exactly seven safe placeholder references.",
  );
  invariant(
    manifest.fields.every(
      (field) =>
        field.sourceTextDisclosure === "withheld_from_offline_packet" &&
        !("tokenText" in field) &&
        !("originalLabel" in field),
    ),
    "Review manifest disclosed source text.",
  );

  const reviewRoot = path.join(outputRoot, "review-packets");
  await mkdir(reviewRoot, { recursive: true });
  await writeJson(
    path.join(reviewRoot, "physician-intent-manifest.json"),
    manifest,
  );
  await writeFile(
    path.join(reviewRoot, "physician-intent-worksheet.html"),
    renderPhysicianIntentWorksheetHtml(manifest),
    "utf8",
  );
  await writeJson(
    path.join(reviewRoot, "physician-intent-decision.schema.json"),
    PHYSICIAN_INTENT_DECISION_JSON_SCHEMA,
  );
  await writeFile(
    path.join(reviewRoot, "static-media-review-worksheet.html"),
    renderMediaReviewWorksheetHtml({ sourceCommit }),
    "utf8",
  );
  await writeJson(
    path.join(reviewRoot, "static-media-review-evidence.schema.json"),
    MEDIA_REVIEW_EVIDENCE_JSON_SCHEMA,
  );
  process.stdout.write(
    `${JSON.stringify({ reviewRoot, sourceCommit, placeholderReferences: manifest.fields.length, sourceContentPackaged: false, mediaPackaged: false })}\n`,
  );
}

void main();
