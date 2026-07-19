import { posix as path } from "node:path";

import { createHash } from "node:crypto";

import { failTemplateDocx } from "./errors";
import { resolveTemplateDocxLimits, type TemplateDocxLimits } from "./limits";
import {
  OPC_CONTENT_TYPES_NAMESPACE,
  OPC_RELATIONSHIPS_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  WORDPROCESSINGML_2012_NAMESPACE,
  WORDPROCESSINGML_NAMESPACE,
  exactExpandedAttribute,
  expandedXmlVisits,
  parseOrderedXml,
  visibleText,
  type ExpandedXmlVisit,
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
const HARMLESS_FIELD_INSTRUCTIONS = new Set([
  "DATE",
  "FORMCHECKBOX",
  "FORMDROPDOWN",
  "FORMTEXT",
  "NUMPAGES",
  "PAGE",
  "SECTION",
  "SECTIONPAGES",
  "TIME",
]);

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
    // Word comments are not part of the rendered document surface and can
    // retain names, clinical text, and deleted content that a reviewer does
    // not see in the ordinary page view. They are outside the supported
    // template boundary rather than silently copied into every output.
    if (
      /^word\/comments(?:Extended|Extensible|Ids)?\.xml$/i.test(name) ||
      /^word\/people\.xml$/i.test(name)
    ) {
      failTemplateDocx("XML_HIDDEN_CONTENT_UNSUPPORTED");
    }
    if (name.endsWith(".xml") || name.endsWith(".rels")) {
      const tree = parseOrderedXml(entry.bytes, limits);
      assertNoHiddenWordContent(tree);
      assertHarmlessWordFieldInstructions(tree);
      if (/^word\/.*\.xml$/i.test(name)) {
        assertNoNamespaceShadowedWordStructures(tree);
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

  for (const node of opcDocumentChildren(
    tree,
    OPC_CONTENT_TYPES_NAMESPACE,
    "Types",
    new Set(["Default", "Override"]),
    "OPC_CONTENT_TYPE_INVALID",
  )) {
    if (node.localName !== "Default") continue;
    const extension = opcAttribute(node, "Extension", true)?.toLowerCase();
    const contentType = opcAttribute(node, "ContentType", true);
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
  for (const node of opcDocumentChildren(
    tree,
    OPC_CONTENT_TYPES_NAMESPACE,
    "Types",
    new Set(["Default", "Override"]),
    "OPC_CONTENT_TYPE_INVALID",
  )) {
    if (node.localName !== "Override") continue;
    const rawPartName = opcAttribute(node, "PartName", true);
    const contentType = opcAttribute(node, "ContentType", true);
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

  for (const node of opcDocumentChildren(
    tree,
    OPC_RELATIONSHIPS_NAMESPACE,
    "Relationships",
    new Set(["Relationship"]),
    "OPC_RELATIONSHIP_INVALID",
  )) {
    const id = opcAttribute(node, "Id", true);
    const type = opcAttribute(node, "Type", true);
    const target = opcAttribute(node, "Target", true);
    const targetMode = opcAttribute(node, "TargetMode", false);
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
  // Safe-alpha has no relationship type that needs a target fragment or
  // query. Reject rather than discard it: otherwise identifier-bearing text
  // after `#`/`?` would survive in the immutable relationship part without
  // participating in target validation.
  const target = rawTarget;
  if (
    !target ||
    target.includes("#") ||
    target.includes("?") ||
    target.includes("\\") ||
    /%(?:2e|2f|5c)/i.test(target)
  ) {
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

function opcDocumentChildren(
  tree: OrderedXmlNode[],
  namespaceUri: string,
  rootLocalName: string,
  allowedChildren: ReadonlySet<string>,
  errorCode: "OPC_CONTENT_TYPE_INVALID" | "OPC_RELATIONSHIP_INVALID",
): ExpandedXmlVisit[] {
  const visits = expandedXmlVisits(tree);
  const roots = visits.filter((visit) => visit.depth === 0);
  if (
    roots.length !== 1 ||
    roots[0]!.namespaceUri !== namespaceUri ||
    roots[0]!.localName !== rootLocalName
  ) {
    failTemplateDocx(errorCode);
  }
  const root = roots[0]!;
  const children = visits.filter((visit) => visit.parent === root);
  if (
    children.some(
      (visit) =>
        visit.namespaceUri !== namespaceUri ||
        !allowedChildren.has(visit.localName),
    ) ||
    visits.some((visit) => visit.depth > 1)
  ) {
    failTemplateDocx(errorCode);
  }
  return children;
}

function opcAttribute(
  visit: ExpandedXmlVisit,
  localName: string,
  required: boolean,
): string | undefined {
  const matching = visit.attributes.filter(
    (attribute) => attribute.localName === localName,
  );
  if (
    matching.length > 1 ||
    (matching.length === 1 && matching[0]!.namespaceUri !== null) ||
    (required && matching.length !== 1)
  ) {
    failTemplateDocx(
      visit.localName === "Relationship"
        ? "OPC_RELATIONSHIP_INVALID"
        : "OPC_CONTENT_TYPE_INVALID",
    );
  }
  return matching.length === 1
    ? exactExpandedAttribute(visit, null, localName)
    : undefined;
}

function assertHarmlessWordFieldInstructions(tree: OrderedXmlNode[]): void {
  const visits = expandedXmlVisits(tree);
  const active: string[][] = [];
  for (const visit of visits) {
    if (visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
    if (visit.localName === "fldSimple") {
      const instruction = exactWordAttribute(visit, "instr");
      if (!instruction) failTemplateDocx("ACTIVE_CONTENT_REJECTED");
      assertHarmlessFieldInstruction(instruction);
      continue;
    }
    if (visit.localName === "fldChar") {
      const type = exactWordAttribute(visit, "fldCharType");
      if (type === "begin") active.push([]);
      else if (type === "end") {
        const fragments = active.pop();
        if (fragments && fragments.length > 0) {
          assertHarmlessFieldInstruction(fragments.join(""));
        }
      }
      continue;
    }
    if (visit.localName === "instrText") {
      const text = visibleText(visit.node);
      if (active.length > 0) active.at(-1)!.push(text);
      else assertHarmlessFieldInstruction(text);
    }
  }
  if (active.length > 0) failTemplateDocx("ACTIVE_CONTENT_REJECTED");
}

const HIDDEN_WORD_ELEMENTS = new Set([
  // Run properties that suppress text in Word or its web layout.
  "specVanish",
  "vanish",
  "webHidden",
  // Revision containers preserve text that is absent from the ordinary
  // accepted document surface. Accepting insertions is also intentionally
  // unsupported: a template must first be saved with revisions resolved.
  "del",
  "ins",
  "moveFrom",
  "moveFromRangeEnd",
  "moveFromRangeStart",
  "moveTo",
  "moveToRangeEnd",
  "moveToRangeStart",
]);

function assertNoHiddenWordContent(tree: OrderedXmlNode[]): void {
  for (const visit of expandedXmlVisits(tree)) {
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      HIDDEN_WORD_ELEMENTS.has(visit.localName)
    ) {
      failTemplateDocx("XML_HIDDEN_CONTENT_UNSUPPORTED");
    }
  }
}

const WORD_CONTROL_ELEMENTS = new Set([
  "comboBox",
  "date",
  "dateFormat",
  "ddList",
  "dropDownList",
  "ffData",
  "fldChar",
  "fldSimple",
  "instrText",
  "listEntry",
  "listItem",
  "sdt",
  "sdtContent",
  "sdtPr",
  "text",
  "textInput",
]);
const WORD_2010_CONTROL_ELEMENTS = new Set([
  "checkbox",
  "checkedState",
  "uncheckedState",
]);
const WORD_2012_CONTROL_ELEMENTS = new Set([
  "repeatingSection",
  "repeatingSectionItem",
]);

function assertNoNamespaceShadowedWordStructures(
  tree: OrderedXmlNode[],
): void {
  for (const visit of expandedXmlVisits(tree)) {
    if (
      visit.localName === "checked" &&
      visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE &&
      visit.namespaceUri !== WORDPROCESSINGML_2010_NAMESPACE
    ) {
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }
    const expected = WORD_CONTROL_ELEMENTS.has(visit.localName)
      ? WORDPROCESSINGML_NAMESPACE
      : WORD_2010_CONTROL_ELEMENTS.has(visit.localName)
        ? WORDPROCESSINGML_2010_NAMESPACE
        : WORD_2012_CONTROL_ELEMENTS.has(visit.localName)
          ? WORDPROCESSINGML_2012_NAMESPACE
          : null;
    if (expected && visit.namespaceUri !== expected) {
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }
  }
}

function exactWordAttribute(
  visit: ExpandedXmlVisit,
  localName: string,
): string | undefined {
  const matches = visit.attributes.filter(
    (attribute) => attribute.localName === localName,
  );
  if (
    matches.length > 1 ||
    (matches.length === 1 &&
      matches[0]!.namespaceUri !== WORDPROCESSINGML_NAMESPACE)
  ) {
    failTemplateDocx("ACTIVE_CONTENT_REJECTED");
  }
  return matches[0]?.value;
}

function assertHarmlessFieldInstruction(raw: string): void {
  const normalized = raw.trim();
  if (!normalized) return;
  const compact = normalized.replace(/\s+/g, "").toUpperCase();
  const keyword = /^=?([A-Z]+)/.exec(compact)?.[1];
  if (!keyword || !HARMLESS_FIELD_INSTRUCTIONS.has(keyword)) {
    failTemplateDocx("ACTIVE_CONTENT_REJECTED");
  }
}

function unionSorted(...lists: readonly string[][]): string[] {
  return [...new Set(lists.flat())].sort((left, right) =>
    left.localeCompare(right),
  );
}
