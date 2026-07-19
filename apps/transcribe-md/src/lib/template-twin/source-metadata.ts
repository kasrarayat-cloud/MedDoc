import { createHash } from "node:crypto";

import JSZip from "jszip";

import { inspectDocxPackage } from "@/lib/note-template-docx";

export const TEMPLATE_TWIN_METADATA_PROFILE =
  "template-twin-docx-metadata-minimization-v1" as const;

const FIXED_ZIP_DATE = new Date("1980-01-01T00:00:00.000Z");

const MINIMAL_CORE_PROPERTIES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>QuillMD</dc:creator><cp:lastModifiedBy>QuillMD</cp:lastModifiedBy></cp:coreProperties>`;

const MINIMAL_EXTENDED_PROPERTIES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Microsoft Office Word</Application></Properties>`;

const EMPTY_CUSTOM_PROPERTIES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"/>`;

const REPLACEMENTS = new Map<string, string>([
  ["docProps/core.xml", MINIMAL_CORE_PROPERTIES],
  ["docProps/app.xml", MINIMAL_EXTENDED_PROPERTIES],
  ["docProps/custom.xml", EMPTY_CUSTOM_PROPERTIES],
]);

export interface TemplateTwinMetadataEvidence {
  readonly profileVersion: typeof TEMPLATE_TWIN_METADATA_PROFILE;
  readonly originalSha256: string;
  readonly minimizedSha256: string;
  readonly replacedParts: readonly string[];
  readonly zipEntryTimestampsNormalized: true;
}

export interface MinimizedTemplateTwinSource {
  readonly document: Buffer;
  readonly evidence: TemplateTwinMetadataEvidence;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Verify the persisted metadata receipt against both immutable byte sets. */
export function isTemplateTwinMetadataEvidenceValid(input: {
  evidence: unknown;
  originalSha256: string;
  minimizedSha256: string;
}): input is {
  evidence: TemplateTwinMetadataEvidence;
  originalSha256: string;
  minimizedSha256: string;
} {
  if (!isRecord(input.evidence)) return false;
  const evidence = input.evidence;
  const replacedParts = evidence.replacedParts;
  return Boolean(
    evidence.profileVersion === TEMPLATE_TWIN_METADATA_PROFILE &&
      evidence.originalSha256 === input.originalSha256 &&
      evidence.minimizedSha256 === input.minimizedSha256 &&
      evidence.zipEntryTimestampsNormalized === true &&
      Array.isArray(replacedParts) &&
      replacedParts.every(
        (part) =>
          typeof part === "string" &&
          (part === "docProps/core.xml" ||
            part === "docProps/app.xml" ||
            part === "docProps/custom.xml"),
      ) &&
      new Set(replacedParts).size === replacedParts.length &&
      [...replacedParts]
        .sort()
        .every((part, index) => part === replacedParts[index]),
  );
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * Replace identity-bearing package properties and normalize ZIP timestamps.
 *
 * The unmodified upload must already have been captured in the private intake
 * quarantine before this function is called. The minimized package becomes
 * the immutable admitted source used for compilation and rendering, so layout
 * parts are never rewritten merely to remove author metadata.
 */
export async function minimizeTemplateTwinSourceMetadata(
  source: Uint8Array,
): Promise<MinimizedTemplateTwinSource> {
  // Apply the complete untrusted-package boundary before passing the archive
  // to JSZip. This bounds entry count, expansion, paths, XML, relationships,
  // active content, hidden content, and malformed package structures.
  inspectDocxPackage(source);

  const zip = await JSZip.loadAsync(source, {
    checkCRC32: true,
    createFolders: false,
  });
  const replacedParts: string[] = [];
  for (const [partName, replacement] of REPLACEMENTS) {
    const entry = zip.file(partName);
    if (!entry) continue;
    zip.file(partName, replacement, {
      binary: false,
      createFolders: false,
      date: FIXED_ZIP_DATE,
    });
    replacedParts.push(partName);
  }

  for (const entry of Object.values(zip.files)) {
    entry.date = FIXED_ZIP_DATE;
    entry.comment = "";
  }

  const document = await zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
    platform: "DOS",
    streamFiles: false,
    comment: "",
  });
  inspectDocxPackage(document);

  return {
    document,
    evidence: Object.freeze({
      profileVersion: TEMPLATE_TWIN_METADATA_PROFILE,
      originalSha256: sha256(source),
      minimizedSha256: sha256(document),
      replacedParts: Object.freeze(replacedParts.sort()),
      zipEntryTimestampsNormalized: true,
    }),
  };
}
