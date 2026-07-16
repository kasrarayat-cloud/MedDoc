import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import path from "node:path";

import JSZip from "jszip";

import { inspectDocxPackage } from "../../note-template-docx/package-security";

export const HUMAN_GATE_ALLOWED_EXTENSIONS = Object.freeze([
  ".cmd",
  ".docx",
  ".html",
  ".json",
  ".pdf",
  ".ps1",
  ".sha256",
  ".txt",
]);

const FORBIDDEN_PATHS = [
  /(?:^|\/)\.env(?:\.|$)/iu,
  /\.(?:der|key|p12|pem|pfx)$/iu,
  /(?:^|\/)(?:id_ed25519|id_rsa)(?:\.|$)/iu,
  /wm[\s_-]*iov/iu,
  /(?:^|\/)media(?:\/|$)/iu,
];

const FORBIDDEN_TEXT = [
  { code: "FORBIDDEN_WM_IOV_CONTENT", pattern: /wm[\s_-]*iov/iu },
  {
    code: "PRIVATE_KEY_MARKER",
    pattern: /-----BEGIN [A-Z ]*PRIVATE KEY-----/u,
  },
  { code: "AWS_ACCESS_KEY_SHAPE", pattern: /\bAKIA[0-9A-Z]{16}\b/u },
  { code: "OPENAI_KEY_SHAPE", pattern: /\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b/u },
  {
    code: "DATABASE_DSN",
    pattern: /\b(?:postgres(?:ql)?|mysql):\/\/[^\s"']+/iu,
  },
  {
    code: "AUTHORIZATION_HEADER",
    pattern: /\bAuthorization\s*:\s*Bearer\s+\S+/iu,
  },
  { code: "SSN_SHAPE", pattern: /\b\d{3}-\d{2}-\d{4}\b/u },
  {
    code: "MRN_SHAPE",
    pattern: /\b(?:MRN|medical record)\s*[:#-]?\s*\d{4,}\b/iu,
  },
  {
    code: "DOB_SHAPE",
    pattern:
      /\b(?:DOB|date of birth)\s*[:#-]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b/iu,
  },
  {
    code: "PHONE_SHAPE",
    pattern: /\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/u,
  },
];

const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b/giu;
const RESERVED_EMAIL_DOMAINS = ["example.test", "synthetic.test"];
const SYNTHETIC_DOCX_PART_ALLOWLIST = new Set([
  "[Content_Types].xml",
  "_rels/.rels",
  "docProps/app.xml",
  "docProps/core.xml",
  "word/_rels/document.xml.rels",
  "word/document.xml",
  "word/footer1.xml",
  "word/fontTable.xml",
  "word/header1.xml",
  "word/numbering.xml",
  "word/settings.xml",
  "word/styles.xml",
]);

export interface HumanGateHygieneIssue {
  readonly code: string;
  readonly relativePath: string;
  readonly detail: string;
}

export interface HumanGateHygieneReport {
  readonly safe: boolean;
  readonly filesScanned: number;
  readonly docxEntriesScanned: number;
  readonly issues: readonly HumanGateHygieneIssue[];
}

function safeRelativePath(root: string, file: string): string {
  const relative = path.relative(root, file).split(path.sep).join("/");
  if (
    !relative ||
    relative.startsWith("/") ||
    relative.includes("\\") ||
    relative.split("/").some((segment) => segment === ".." || segment === "")
  ) {
    throw new Error(`TT_HUMAN_GATE_UNSAFE_PATH:${relative}`);
  }
  return relative;
}

function scanText(relativePath: string, text: string): HumanGateHygieneIssue[] {
  const issues: HumanGateHygieneIssue[] = [];
  for (const rule of FORBIDDEN_TEXT) {
    if (rule.pattern.test(text)) {
      issues.push({
        code: rule.code,
        relativePath,
        detail: "Forbidden high-signal content detected.",
      });
    }
  }
  for (const match of text.matchAll(EMAIL_PATTERN)) {
    const domain = match[1].toLocaleLowerCase("en-US");
    if (!RESERVED_EMAIL_DOMAINS.includes(domain)) {
      issues.push({
        code: "NON_RESERVED_EMAIL_ADDRESS",
        relativePath,
        detail: "Only example.test and synthetic.test addresses are permitted.",
      });
      break;
    }
  }
  return issues;
}

function scanPdfContainerStrings(
  relativePath: string,
  text: string,
): HumanGateHygieneIssue[] {
  const issues: HumanGateHygieneIssue[] = [];
  // Phone/date/identifier-shaped byte sequences are not meaningful in a
  // compressed PDF stream (xref and deflate bytes produce false positives).
  // Clinical text is scanned in the independently inspected source DOCX from
  // which this exact-hash PDF was derived. Here we still reject literal source
  // markers, secrets, credentials, and non-reserved email addresses.
  for (const rule of FORBIDDEN_TEXT.slice(0, 6)) {
    if (rule.pattern.test(text)) {
      issues.push({
        code: rule.code,
        relativePath,
        detail: "Forbidden literal content detected in PDF container bytes.",
      });
    }
  }
  for (const match of text.matchAll(EMAIL_PATTERN)) {
    const domain = match[1].toLocaleLowerCase("en-US");
    if (!RESERVED_EMAIL_DOMAINS.includes(domain)) {
      issues.push({
        code: "NON_RESERVED_EMAIL_ADDRESS",
        relativePath,
        detail: "Only reserved synthetic email domains are allowed.",
      });
      break;
    }
  }
  return issues;
}

async function scanDocx(
  relativePath: string,
  bytes: Buffer,
): Promise<{
  issues: HumanGateHygieneIssue[];
  entries: number;
}> {
  const issues: HumanGateHygieneIssue[] = [];
  if (bytes.length < 4 || bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
    return {
      entries: 0,
      issues: [
        {
          code: "DOCX_MAGIC_MISMATCH",
          relativePath,
          detail: "DOCX is not an OPC ZIP package.",
        },
      ],
    };
  }
  let zip: JSZip;
  try {
    inspectDocxPackage(bytes);
  } catch (error) {
    return {
      entries: 0,
      issues: [
        {
          code: "PRODUCTION_PACKAGE_INSPECTION_FAILED",
          relativePath,
          detail:
            error instanceof Error && "code" in error
              ? String((error as Error & { code: unknown }).code)
              : "Production DOCX inspection rejected the package.",
        },
      ],
    };
  }
  try {
    zip = await JSZip.loadAsync(bytes, { checkCRC32: true });
  } catch {
    return {
      entries: 0,
      issues: [
        {
          code: "DOCX_PACKAGE_INVALID",
          relativePath,
          detail: "DOCX package could not be parsed.",
        },
      ],
    };
  }
  const names = Object.keys(zip.files).sort();
  for (const name of names) {
    if (zip.files[name].dir) continue;
    if (
      name.startsWith("/") ||
      name.includes("\\") ||
      name.split("/").some((segment) => segment === "..")
    ) {
      issues.push({
        code: "DOCX_ENTRY_PATH_UNSAFE",
        relativePath,
        detail: `Unsafe OPC entry: ${name}`,
      });
      continue;
    }
    if (!SYNTHETIC_DOCX_PART_ALLOWLIST.has(name)) {
      issues.push({
        code: "DOCX_PART_NOT_ALLOWLISTED",
        relativePath,
        detail: `Synthetic release-gate corpus does not allow this OPC part: ${name}`,
      });
      continue;
    }
    if (/\.(?:xml|rels)$/iu.test(name)) {
      const content = await zip.files[name].async("string");
      issues.push(...scanText(`${relativePath}!/${name}`, content));
    }
  }
  return { issues, entries: names.length };
}

export async function scanHumanGateDirectory(
  root: string,
  options: { readonly forbiddenFileSha256?: readonly string[] } = {},
): Promise<HumanGateHygieneReport> {
  const issues: HumanGateHygieneIssue[] = [];
  const files: string[] = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      const metadata = await lstat(file);
      const relativePath = safeRelativePath(root, file);
      if (metadata.isSymbolicLink()) {
        issues.push({
          code: "SYMLINK_FORBIDDEN",
          relativePath,
          detail: "Artifacts must contain regular files only.",
        });
      } else if (metadata.isDirectory()) {
        await walk(file);
      } else if (metadata.isFile()) {
        files.push(file);
      } else {
        issues.push({
          code: "NON_REGULAR_FILE",
          relativePath,
          detail: "Unsupported filesystem entry.",
        });
      }
    }
  }
  await walk(root);
  let docxEntriesScanned = 0;
  for (const file of files.sort()) {
    const relativePath = safeRelativePath(root, file);
    if (FORBIDDEN_PATHS.some((pattern) => pattern.test(relativePath))) {
      issues.push({
        code: "FORBIDDEN_FILENAME",
        relativePath,
        detail: "Forbidden filename or directory.",
      });
      continue;
    }
    const extension = path.extname(relativePath).toLocaleLowerCase("en-US");
    if (!HUMAN_GATE_ALLOWED_EXTENSIONS.includes(extension)) {
      issues.push({
        code: "BINARY_NOT_ALLOWLISTED",
        relativePath,
        detail: `Extension ${extension || "(none)"} is not allowed.`,
      });
      continue;
    }
    const bytes = await readFile(file);
    if (options.forbiddenFileSha256?.includes(sha256(bytes))) {
      issues.push({
        code: "FORBIDDEN_SOURCE_BYTES",
        relativePath,
        detail: "Artifact bytes match an explicitly forbidden source document.",
      });
      continue;
    }
    if (extension === ".docx") {
      const docx = await scanDocx(relativePath, bytes);
      issues.push(...docx.issues);
      docxEntriesScanned += docx.entries;
    } else if (extension === ".pdf") {
      if (!bytes.subarray(0, 5).equals(Buffer.from("%PDF-", "ascii"))) {
        issues.push({
          code: "PDF_MAGIC_MISMATCH",
          relativePath,
          detail: "PDF magic bytes are invalid.",
        });
      }
      const ascii = bytes.toString("latin1");
      issues.push(...scanPdfContainerStrings(relativePath, ascii));
      if (
        /\/(?:AA|EmbeddedFile|JavaScript|JS|Launch|OpenAction)\b/u.test(ascii)
      ) {
        issues.push({
          code: "PDF_ACTIVE_OR_EMBEDDED_CONTENT",
          relativePath,
          detail: "Synthetic PDF evidence contains active or embedded content.",
        });
      }
    } else {
      if (bytes.includes(0)) {
        issues.push({
          code: "UNEXPECTED_BINARY_TEXT_FILE",
          relativePath,
          detail: "Text artifact contains NUL bytes.",
        });
      } else {
        issues.push(...scanText(relativePath, bytes.toString("utf8")));
      }
    }
  }
  return {
    safe: issues.length === 0,
    filesScanned: files.length,
    docxEntriesScanned,
    issues,
  };
}

export function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}
