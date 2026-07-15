import { posix as path } from "node:path";

import { createHash } from "node:crypto";

import { failTemplateDocx } from "./errors";
import { resolveTemplateDocxLimits, type TemplateDocxLimits } from "./limits";
import {
  descendants,
  getAttribute,
  parseOrderedXml,
  type OrderedXmlNode,
} from "./xml";
import {
  readVerifiedZipPackage,
  type VerifiedZipPackage,
} from "./zip-directory";

const DOCX_MAIN_CONTENT_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml";
const OFFICE_DOCUMENT_RELATIONSHIP = "/officeDocument";
const HEADER_RELATIONSHIP = "/header";
const FOOTER_RELATIONSHIP = "/footer";

const ACTIVE_PART_RE = /(?:^|\/)(?:vbaProject\.bin|activeX|customUI)(?:\/|$)/i;
const EMBEDDED_PART_RE = /(?:^|\/)(?:embeddings)(?:\/|$)/i;
const SIGNATURE_PART_RE = /(?:^|\/)_xmlsignatures(?:\/|$)/i;
const ACTIVE_CONTENT_TYPE_RE =
  /(?:macroEnabled|vbaProject|activeX|oleObject|alternativeFormatInput|mswordTemplate)/i;
const ACTIVE_RELATIONSHIP_TYPE_RE =
  /\/(?:vbaProject|oleObject|package|activeXControl|attachedTemplate|aFChunk)$/i;
const REMOTE_TARGET_RE = /^(?:[a-z][a-z0-9+.-]*:|\/\/|\\\\)/i;
const ACTIVE_FIELD_INSTRUCTION_RE =
  /\b(?:DDEAUTO|DDE|INCLUDETEXT|INCLUDEPICTURE|DATABASE|LINK)\b/i;

export interface OpcRelationship {
  readonly sourcePartName: string;
  readonly relationshipPartName: string;
  readonly id: string;
  readonly type: string;
  readonly targetPartName: string;
}

export interface InspectedDocxPackage {
  readonly zip: VerifiedZipPackage;
  readonly limits: TemplateDocxLimits;
  readonly mainPartName: "word/document.xml";
  readonly headerPartNames: readonly string[];
  readonly footerPartNames: readonly string[];
  readonly relationships: readonly OpcRelationship[];
  readonly relationshipCounts: ReadonlyMap<string, number>;
  readonly contentTypes: ReadonlyMap<string, string>;
  readonly sourceSha256: string;
}

export function inspectDocxPackage(
  source: Uint8Array,
  limitOverrides?: Partial<TemplateDocxLimits>,
): InspectedDocxPackage {
  const limits = resolveTemplateDocxLimits(limitOverrides);
  const zip = readVerifiedZipPackage(source, limits);

  for (const required of [
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
  ]) {
    if (!zip.entries.has(required))
      failTemplateDocx("OPC_REQUIRED_PART_MISSING");
  }

  for (const [name, entry] of zip.entries) {
    if (ACTIVE_PART_RE.test(name)) failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    if (EMBEDDED_PART_RE.test(name))
      failTemplateDocx("EMBEDDED_OBJECT_REJECTED");
    if (SIGNATURE_PART_RE.test(name))
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    if (name.endsWith(".xml") || name.endsWith(".rels")) {
      const tree = parseOrderedXml(entry.bytes, limits);
      const instructions = extractInstructionText(tree);
      if (
        ACTIVE_FIELD_INSTRUCTION_RE.test(instructions) ||
        ACTIVE_FIELD_INSTRUCTION_RE.test(instructions.replace(/\s+/g, ""))
      ) {
        failTemplateDocx("ACTIVE_CONTENT_REJECTED");
      }
    }
  }

  const contentTypes = parseContentTypes(
    zip.entries.get("[Content_Types].xml")!.bytes,
    zip,
    limits,
  );
  const mainContentType = contentTypes.get("word/document.xml");
  if (mainContentType?.toLowerCase().includes("macroenabled")) {
    failTemplateDocx("DOCM_REJECTED");
  }
  if (mainContentType !== DOCX_MAIN_CONTENT_TYPE) {
    failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
  }

  const relationships: OpcRelationship[] = [];
  const relationshipCounts = new Map<string, number>();
  for (const [name, entry] of [...zip.entries].sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    if (!name.endsWith(".rels")) continue;
    const sourcePartName = relationshipSourcePart(name);
    if (sourcePartName && !zip.entries.has(sourcePartName)) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    const parsed = parseRelationships(
      entry.bytes,
      name,
      sourcePartName,
      zip,
      limits,
    );
    relationships.push(...parsed);
    relationshipCounts.set(sourcePartName || "/", parsed.length);
  }

  const rootOfficeDocuments = relationships.filter(
    (relationship) =>
      relationship.sourcePartName === "" &&
      relationship.type.endsWith(OFFICE_DOCUMENT_RELATIONSHIP),
  );
  if (
    rootOfficeDocuments.length !== 1 ||
    rootOfficeDocuments[0]!.targetPartName !== "word/document.xml"
  ) {
    failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  }

  const documentRelationships = relationships.filter(
    (relationship) => relationship.sourcePartName === "word/document.xml",
  );
  const relatedHeaders = documentRelationships
    .filter((relationship) => relationship.type.endsWith(HEADER_RELATIONSHIP))
    .map((relationship) => relationship.targetPartName);
  const relatedFooters = documentRelationships
    .filter((relationship) => relationship.type.endsWith(FOOTER_RELATIONSHIP))
    .map((relationship) => relationship.targetPartName);

  const headerPartNames = unionSorted(
    relatedHeaders,
    [...zip.entries.keys()].filter((name) =>
      /^word\/header[^/]*\.xml$/i.test(name),
    ),
  );
  const footerPartNames = unionSorted(
    relatedFooters,
    [...zip.entries.keys()].filter((name) =>
      /^word\/footer[^/]*\.xml$/i.test(name),
    ),
  );
  for (const partName of [...headerPartNames, ...footerPartNames]) {
    if (!zip.entries.has(partName))
      failTemplateDocx("OPC_REQUIRED_PART_MISSING");
    const expectedSuffix = headerPartNames.includes(partName)
      ? ".header+xml"
      : ".footer+xml";
    if (!contentTypes.get(partName)?.endsWith(expectedSuffix)) {
      failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    }
  }

  return {
    zip,
    limits,
    mainPartName: "word/document.xml",
    headerPartNames,
    footerPartNames,
    relationships,
    relationshipCounts,
    contentTypes,
    sourceSha256: createHash("sha256").update(zip.source).digest("hex"),
  };
}

function parseContentTypes(
  bytes: Uint8Array,
  zip: VerifiedZipPackage,
  limits: TemplateDocxLimits,
): ReadonlyMap<string, string> {
  const tree = parseOrderedXml(bytes, limits);
  const defaults = new Map<string, string>();
  const overrides = new Map<string, string>();

  for (const node of descendants(tree, "Default")) {
    const extension = getAttribute(node, "Extension")?.toLowerCase();
    const contentType = getAttribute(node, "ContentType");
    if (
      !extension ||
      !/^[a-z0-9]{1,32}$/.test(extension) ||
      !contentType ||
      !isValidContentType(contentType) ||
      defaults.has(extension)
    ) {
      failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    }
    if (ACTIVE_CONTENT_TYPE_RE.test(contentType)) {
      if (/macroEnabled/i.test(contentType)) failTemplateDocx("DOCM_REJECTED");
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }
    defaults.set(extension, contentType);
  }
  for (const node of descendants(tree, "Override")) {
    const rawPartName = getAttribute(node, "PartName");
    const contentType = getAttribute(node, "ContentType");
    if (
      !rawPartName ||
      !rawPartName.startsWith("/") ||
      !contentType ||
      !isValidContentType(contentType)
    ) {
      failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    }
    const partName = rawPartName.slice(1);
    if (
      !isSafePartName(partName) ||
      !zip.entries.has(partName) ||
      overrides.has(partName)
    ) {
      failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    }
    if (ACTIVE_CONTENT_TYPE_RE.test(contentType)) {
      if (/macroEnabled/i.test(contentType)) failTemplateDocx("DOCM_REJECTED");
      if (/oleObject/i.test(contentType))
        failTemplateDocx("EMBEDDED_OBJECT_REJECTED");
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }
    overrides.set(partName, contentType);
  }

  const resolved = new Map<string, string>();
  for (const name of zip.entries.keys()) {
    if (name === "[Content_Types].xml") {
      resolved.set(name, "application/xml");
      continue;
    }
    const extension = name.includes(".")
      ? name.slice(name.lastIndexOf(".") + 1).toLowerCase()
      : "";
    const contentType = overrides.get(name) ?? defaults.get(extension);
    if (!contentType) failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    resolved.set(name, contentType);
  }
  return resolved;
}

function parseRelationships(
  bytes: Uint8Array,
  relationshipPartName: string,
  sourcePartName: string,
  zip: VerifiedZipPackage,
  limits: TemplateDocxLimits,
): OpcRelationship[] {
  const tree = parseOrderedXml(bytes, limits);
  const relationships: OpcRelationship[] = [];
  const ids = new Set<string>();

  for (const node of descendants(tree, "Relationship")) {
    const id = getAttribute(node, "Id");
    const type = getAttribute(node, "Type");
    const target = getAttribute(node, "Target");
    const targetMode = getAttribute(node, "TargetMode");
    if (
      !id ||
      id.length > 240 ||
      id !== id.trim() ||
      !type ||
      type.length > 512 ||
      type !== type.trim() ||
      !/^[a-z][a-z0-9+.-]*:[^\s?#]+$/i.test(type) ||
      !target ||
      target.length > 512 ||
      target !== target.trim() ||
      ids.has(id)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    ids.add(id);
    if (
      targetMode?.toLowerCase() === "external" ||
      REMOTE_TARGET_RE.test(target)
    ) {
      failTemplateDocx("EXTERNAL_RELATIONSHIP_REJECTED");
    }
    if (targetMode && targetMode.toLowerCase() !== "internal") {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    if (ACTIVE_RELATIONSHIP_TYPE_RE.test(type)) {
      if (/\/(?:oleObject|package)$/i.test(type)) {
        failTemplateDocx("EMBEDDED_OBJECT_REJECTED");
      }
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }

    const targetPartName = resolveRelationshipTarget(sourcePartName, target);
    if (!zip.entries.has(targetPartName))
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    relationships.push({
      sourcePartName,
      relationshipPartName,
      id,
      type,
      targetPartName,
    });
  }
  return relationships;
}

function relationshipSourcePart(relationshipPartName: string): string {
  if (relationshipPartName === "_rels/.rels") return "";
  const match = /^(?:(.*)\/)?_rels\/([^/]+)\.rels$/.exec(relationshipPartName);
  if (!match) failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  return match[1] ? `${match[1]}/${match[2]}` : match[2]!;
}

function resolveRelationshipTarget(
  sourcePartName: string,
  rawTarget: string,
): string {
  const target = rawTarget.split("#", 1)[0]!;
  if (!target || target.includes("\\") || /%(?:2e|2f|5c)/i.test(target)) {
    failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  }
  const base = sourcePartName ? path.dirname(sourcePartName) : "";
  const resolved = path.normalize(
    target.startsWith("/") ? target.slice(1) : path.join(base, target),
  );
  if (!isSafePartName(resolved)) failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  return resolved;
}

function isSafePartName(partName: string): boolean {
  return (
    partName.length > 0 &&
    partName.length <= 240 &&
    !partName.startsWith("/") &&
    !partName.startsWith("../") &&
    !partName.includes("/../") &&
    !partName.includes("/./") &&
    !partName.includes("//") &&
    !partName.includes("\\") &&
    !partName.includes("\0") &&
    !/[?#:]/.test(partName) &&
    !/%(?:2e|2f|5c)/i.test(partName) &&
    /^[\x21-\x7e]+$/.test(partName)
  );
}

function isValidContentType(contentType: string): boolean {
  return (
    contentType.length <= 240 &&
    /^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+$/i.test(contentType)
  );
}

function extractInstructionText(tree: OrderedXmlNode[]): string {
  return descendants(tree, "instrText")
    .map((node) => {
      const values = node[Object.keys(node).find((key) => key !== ":@") ?? ""];
      if (!Array.isArray(values)) return "";
      return values
        .map((child) => String((child as OrderedXmlNode)["#text"] ?? ""))
        .join("");
    })
    .join(" ");
}

function unionSorted(...lists: readonly string[][]): string[] {
  return [...new Set(lists.flat())].sort((left, right) =>
    left.localeCompare(right),
  );
}
