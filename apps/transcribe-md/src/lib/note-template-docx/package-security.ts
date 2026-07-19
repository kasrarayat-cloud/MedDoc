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
const DOCX_HEADER_CONTENT_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml";
const DOCX_FOOTER_CONTENT_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml";
const OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE =
  "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const OFFICE_DOCUMENT_RELATIONSHIP = `${OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE}/officeDocument`;
const HEADER_RELATIONSHIP = `${OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE}/header`;
const FOOTER_RELATIONSHIP = `${OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE}/footer`;

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

  const wordHeaderRootParts = new Set<string>();
  const wordFooterRootParts = new Set<string>();
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
      if (/^word\/.*\.xml$/i.test(name)) {
        assertNoNamespaceShadowedWordStructures(tree);
        assertDeterministicWordControlShape(tree);
        assertHarmlessWordFieldInstructions(tree);
        const roots = expandedXmlVisits(tree).filter(
          (visit) => visit.depth === 0,
        );
        if (
          roots.length === 1 &&
          roots[0]!.namespaceUri === WORDPROCESSINGML_NAMESPACE
        ) {
          if (roots[0]!.localName === "hdr") wordHeaderRootParts.add(name);
          if (roots[0]!.localName === "ftr") wordFooterRootParts.add(name);
        }
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
      relationship.type === OFFICE_DOCUMENT_RELATIONSHIP,
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
  const { headerPartNames, footerPartNames } = resolveReferencedStoryParts({
    document: parseOrderedXml(
      zip.entries.get("word/document.xml")!.bytes,
      limits,
    ),
    documentRelationships,
    contentTypes,
  });
  for (const partName of [...headerPartNames, ...footerPartNames]) {
    if (!zip.entries.has(partName))
      failTemplateDocx("OPC_REQUIRED_PART_MISSING");
    const isHeader = headerPartNames.includes(partName);
    const expectedContentType = isHeader
      ? DOCX_HEADER_CONTENT_TYPE
      : DOCX_FOOTER_CONTENT_TYPE;
    if (contentTypes.get(partName) !== expectedContentType) {
      failTemplateDocx("OPC_CONTENT_TYPE_INVALID");
    }
    if (
      isHeader
        ? !wordHeaderRootParts.has(partName)
        : !wordFooterRootParts.has(partName)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
  }
  const referencedHeaders = new Set(headerPartNames);
  const referencedFooters = new Set(footerPartNames);
  for (const partName of zip.entries.keys()) {
    const headerLikeName = /^word\/header[^/]*\.xml$/iu.test(partName);
    const footerLikeName = /^word\/footer[^/]*\.xml$/iu.test(partName);
    if (
      (headerLikeName || wordHeaderRootParts.has(partName)) &&
      !referencedHeaders.has(partName)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    if (
      (footerLikeName || wordFooterRootParts.has(partName)) &&
      !referencedFooters.has(partName)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
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
  // Property/table revision payloads preserve an earlier document state that
  // is not part of the physician-visible accepted surface.
  "cellDel",
  "cellIns",
  "cellMerge",
  "numberingChange",
  "pPrChange",
  "rPrChange",
  "sectPrChange",
  "tblGridChange",
  "tblPrChange",
  "tblPrExChange",
  "tcPrChange",
  "trPrChange",
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
  "alias",
  "bookmarkStart",
  "bibliography",
  "calendar",
  "calcOnExit",
  "checkBox",
  "citation",
  "comboBox",
  "dataBinding",
  "date",
  "dateFormat",
  "ddList",
  "default",
  "docPartCategory",
  "docPartGallery",
  "docPartList",
  "docPartObj",
  "docPartUnique",
  "dropDownList",
  "enabled",
  "entryMacro",
  "equation",
  "exitMacro",
  "ffData",
  "fldChar",
  "fldSimple",
  "footerReference",
  "format",
  "gridAfter",
  "gridBefore",
  "gridCol",
  "gridSpan",
  "group",
  "hMerge",
  "headerReference",
  "helpText",
  "id",
  "instrText",
  "lastValue",
  "label",
  "lid",
  "listEntry",
  "listItem",
  "lock",
  "maxLength",
  "name",
  "numPr",
  "picture",
  "placeholder",
  "result",
  "richText",
  "sdt",
  "sdtContent",
  "sdtPr",
  "sectPr",
  "showingPlcHdr",
  "size",
  "sizeAuto",
  "statusText",
  "storeMappedDataAs",
  "tabIndex",
  "temporary",
  "tag",
  "tbl",
  "tblGrid",
  "tcPr",
  "text",
  "textInput",
  "tr",
  "type",
  "vMerge",
]);
const WORD_2010_CONTROL_ELEMENTS = new Set([
  "checkbox",
  "checkedState",
  "entityPicker",
  "uncheckedState",
]);
const WORD_2012_CONTROL_ELEMENTS = new Set([
  "repeatingSection",
  "repeatingSectionItem",
]);

const WORD_CONTROL_ATTRIBUTE_POLICY = new Map<string, ReadonlySet<string>>(
  [
    ...([
      ["alias", ["val"]],
      ["tag", ["val"]],
      ["id", ["val"]],
      ["name", ["val"]],
      ["type", ["val"]],
      ["default", ["val"]],
      ["format", ["val"]],
      ["maxLength", ["val"]],
      ["result", ["val"]],
      ["checked", ["val"]],
      ["calcOnExit", ["val"]],
      ["enabled", ["val"]],
      ["entryMacro", ["val"]],
      ["exitMacro", ["val"]],
      ["helpText", ["type", "val"]],
      ["label", ["val"]],
      ["listEntry", ["val"]],
      ["listItem", ["displayText", "value"]],
      ["size", ["val"]],
      ["statusText", ["type", "val"]],
      ["tabIndex", ["val"]],
      ["date", ["fullDate"]],
      ["dateFormat", ["val"]],
      ["lid", ["val"]],
      ["calendar", ["val"]],
      ["storeMappedDataAs", ["val"]],
      ["lastValue", ["val"]],
      ["docPartCategory", ["val"]],
      ["docPartGallery", ["val"]],
      ["lock", ["val"]],
      ["text", ["multiLine"]],
      ["rStyle", ["val"]],
      ["gridCol", ["w"]],
      ["gridSpan", ["val"]],
      ["vMerge", ["val"]],
      ["bookmarkStart", ["name"]],
      ["fldChar", ["fldCharType"]],
      ["fldSimple", ["instr"]],
    ] as const),
  ].map(([element, attributes]) => [
    `${WORDPROCESSINGML_NAMESPACE}\0${element}`,
    new Set(attributes),
  ]),
);

for (const element of ["checked", "checkedState", "uncheckedState"]) {
  WORD_CONTROL_ATTRIBUTE_POLICY.set(
    `${WORDPROCESSINGML_2010_NAMESPACE}\0${element}`,
    new Set(["val"]),
  );
}

function assertNoNamespaceShadowedWordStructures(tree: OrderedXmlNode[]): void {
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
    const attributePolicy = WORD_CONTROL_ATTRIBUTE_POLICY.get(
      `${visit.namespaceUri ?? ""}\0${visit.localName}`,
    );
    if (attributePolicy) {
      for (const localName of attributePolicy) {
        const matches = visit.attributes.filter(
          (attribute) => attribute.localName === localName,
        );
        if (
          matches.length > 1 ||
          (matches.length === 1 &&
            matches[0]!.namespaceUri !== visit.namespaceUri)
        ) {
          failTemplateDocx("ACTIVE_CONTENT_REJECTED");
        }
      }
    }
  }
}

const WORD_SDT_MAIN_TYPES = new Set([
  "bibliography",
  "citation",
  "comboBox",
  "date",
  "docPartList",
  "docPartObj",
  "dropDownList",
  "equation",
  "group",
  "picture",
  "richText",
  "text",
]);

const WORD_SDT_METADATA_CHILDREN = new Set([
  "alias",
  "dataBinding",
  "id",
  "lock",
  "placeholder",
  "showingPlcHdr",
  "tag",
  "temporary",
]);
const WORD_DOC_PART_CHILDREN = new Set([
  "docPartCategory",
  "docPartGallery",
  "docPartUnique",
]);
const WORD_DATE_CHILDREN = new Set([
  "calendar",
  "dateFormat",
  "storeMappedDataAs",
]);
const WORD_LEGACY_FORM_CHILDREN = new Set([
  "calcOnExit",
  "enabled",
  "helpText",
  "label",
  "statusText",
  "tabIndex",
]);
const WORD_LEGACY_CHECKBOX_CHILDREN = new Set(["checked", "size", "sizeAuto"]);
const WORD_LEGACY_DROPDOWN_CHILDREN = new Set(["listEntry", "result"]);
const WORD_LEGACY_TEXT_CHILDREN = new Set(["format", "maxLength"]);

function assertDeterministicWordControlShape(tree: OrderedXmlNode[]): void {
  const visits = expandedXmlVisits(tree);
  for (const visit of visits) {
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["entryMacro", "exitMacro", "fieldMapData", "mailMerge", "odso"].includes(
        visit.localName,
      )
    ) {
      failTemplateDocx("ACTIVE_CONTENT_REJECTED");
    }
    if (isWordSdtTypeElement(visit)) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "sdtPr"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["checkBox", "ddList", "textInput"].includes(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "ffData"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["sdtPr", "sdtContent"].includes(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "sdt"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "ffData"
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "fldChar"]],
        "XML_INVALID",
      );
      if (exactWordAttribute(visit.parent!, "fldCharType") !== "begin") {
        failTemplateDocx("XML_INVALID");
      }
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["fldChar", "instrText"].includes(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "r"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "fldSimple"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "bdo"],
          [WORDPROCESSINGML_NAMESPACE, "customXml"],
          [WORDPROCESSINGML_NAMESPACE, "dir"],
          [WORDPROCESSINGML_NAMESPACE, "fldSimple"],
          [WORDPROCESSINGML_NAMESPACE, "hyperlink"],
          [WORDPROCESSINGML_NAMESPACE, "p"],
          [WORDPROCESSINGML_NAMESPACE, "rt"],
          [WORDPROCESSINGML_NAMESPACE, "rubyBase"],
          [WORDPROCESSINGML_NAMESPACE, "sdtContent"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_SDT_METADATA_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "sdtPr"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "listItem"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "comboBox"],
          [WORDPROCESSINGML_NAMESPACE, "dropDownList"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_DOC_PART_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "docPartList"],
          [WORDPROCESSINGML_NAMESPACE, "docPartObj"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "lastValue"
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "comboBox"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_DATE_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "date"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "lid"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "date"],
          [WORDPROCESSINGML_NAMESPACE, "rubyPr"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      ["checked", "checkedState", "uncheckedState"].includes(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_2010_NAMESPACE, "checkbox"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_LEGACY_FORM_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "ffData"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_LEGACY_CHECKBOX_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "checkBox"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_LEGACY_DROPDOWN_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "ddList"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_LEGACY_TEXT_CHILDREN.has(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "textInput"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "type"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "sectPr"],
          [WORDPROCESSINGML_NAMESPACE, "textInput"],
          [WORDPROCESSINGML_NAMESPACE, "types"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "default"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "checkBox"],
          [WORDPROCESSINGML_NAMESPACE, "ddList"],
          [WORDPROCESSINGML_NAMESPACE, "textInput"],
        ],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "name" &&
      nearestWordAncestor(visit, "ffData")
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "ffData"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "tblGrid"
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "tbl"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "gridCol"
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "tblGrid"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["gridSpan", "hMerge", "vMerge"].includes(visit.localName)
    ) {
      requireDirectParent(
        visit,
        [[WORDPROCESSINGML_NAMESPACE, "tcPr"]],
        "XML_INVALID",
      );
    }
    if (
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "tcPr"
    ) {
      requireDirectParent(
        visit,
        [
          [WORDPROCESSINGML_NAMESPACE, "style"],
          [WORDPROCESSINGML_NAMESPACE, "tblStylePr"],
          [WORDPROCESSINGML_NAMESPACE, "tc"],
        ],
        "XML_INVALID",
      );
    }
  }
  for (const properties of visits) {
    if (
      properties.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      properties.localName !== "sdtPr"
    ) {
      continue;
    }
    const children = visits.filter((visit) => visit.parent === properties);
    const typeChildren = children.filter((child) =>
      isWordSdtTypeElement(child),
    );
    if (typeChildren.length > 1) failTemplateDocx("XML_INVALID");

    for (const singleton of [
      "alias",
      "dataBinding",
      "id",
      "lock",
      "placeholder",
      "showingPlcHdr",
      "tag",
      "temporary",
    ]) {
      if (
        children.filter(
          (child) =>
            child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
            child.localName === singleton,
        ).length > 1
      ) {
        failTemplateDocx("XML_INVALID");
      }
    }
  }

  for (const contentControl of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "sdt",
  )) {
    const children = visits.filter((visit) => visit.parent === contentControl);
    for (const required of ["sdtPr", "sdtContent"]) {
      if (
        children.filter(
          (child) =>
            child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
            child.localName === required,
        ).length !== 1
      ) {
        failTemplateDocx("XML_INVALID");
      }
    }
  }

  for (const docPart of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["docPartList", "docPartObj"].includes(visit.localName),
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === docPart),
      ["docPartCategory", "docPartGallery", "docPartUnique"],
    );
  }

  for (const comboBox of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "comboBox",
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === comboBox),
      ["lastValue"],
    );
  }

  for (const checkbox of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      visit.localName === "checkbox",
  )) {
    assertSingletonChildren(
      visits.filter((visit) => visit.parent === checkbox),
      WORDPROCESSINGML_2010_NAMESPACE,
      ["checked", "checkedState", "uncheckedState"],
    );
  }

  for (const date of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "date",
  )) {
    const children = visits.filter((visit) => visit.parent === date);
    for (const singleton of [
      "dateFormat",
      "lid",
      "calendar",
      "storeMappedDataAs",
    ]) {
      if (
        children.filter(
          (child) =>
            child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
            child.localName === singleton,
        ).length > 1
      ) {
        failTemplateDocx("XML_INVALID");
      }
    }
  }

  for (const formData of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "ffData",
  )) {
    const children = visits.filter((visit) => visit.parent === formData);
    const controlChildren = children.filter(
      (child) =>
        child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        ["checkBox", "ddList", "textInput"].includes(child.localName),
    );
    if (controlChildren.length !== 1) failTemplateDocx("XML_INVALID");
    assertSingletonWordChildren(children, [
      "calcOnExit",
      "enabled",
      "entryMacro",
      "exitMacro",
      "helpText",
      "label",
      "name",
      "statusText",
      "tabIndex",
    ]);
  }

  for (const textInput of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "textInput",
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === textInput),
      ["default", "format", "maxLength", "type"],
    );
  }

  for (const dropdown of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "ddList",
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === dropdown),
      ["default", "result"],
    );
  }

  for (const checkbox of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "checkBox",
  )) {
    const children = visits.filter((visit) => visit.parent === checkbox);
    assertSingletonWordChildren(children, [
      "checked",
      "default",
      "size",
      "sizeAuto",
    ]);
    if (
      children.some(
        (child) =>
          child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          child.localName === "size",
      ) &&
      children.some(
        (child) =>
          child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          child.localName === "sizeAuto",
      )
    ) {
      failTemplateDocx("XML_INVALID");
    }
  }

  for (const cellProperties of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "tcPr",
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === cellProperties),
      ["gridSpan", "hMerge", "vMerge"],
    );
  }

  for (const table of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "tbl",
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === table),
      ["tblGrid"],
    );
  }

  for (const parent of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["style", "tblStylePr", "tc"].includes(visit.localName),
  )) {
    assertSingletonWordChildren(
      visits.filter((visit) => visit.parent === parent),
      ["tcPr"],
    );
  }
}

function requireDirectParent(
  visit: ExpandedXmlVisit,
  allowedParents: readonly (readonly [string, string])[],
  errorCode: "ACTIVE_CONTENT_REJECTED" | "XML_INVALID",
): void {
  if (
    !visit.parent ||
    !allowedParents.some(
      ([namespaceUri, localName]) =>
        visit.parent?.namespaceUri === namespaceUri &&
        visit.parent.localName === localName,
    )
  ) {
    failTemplateDocx(errorCode);
  }
}

function nearestWordAncestor(
  visit: ExpandedXmlVisit,
  localName: string,
): ExpandedXmlVisit | null {
  let current = visit.parent;
  while (current) {
    if (
      current.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      current.localName === localName
    ) {
      return current;
    }
    current = current.parent;
  }
  return null;
}

function isWordSdtTypeElement(visit: ExpandedXmlVisit): boolean {
  return (
    (visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      WORD_SDT_MAIN_TYPES.has(visit.localName)) ||
    (visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      ["checkbox", "entityPicker"].includes(visit.localName)) ||
    (visit.namespaceUri === WORDPROCESSINGML_2012_NAMESPACE &&
      WORD_2012_CONTROL_ELEMENTS.has(visit.localName))
  );
}

function assertSingletonWordChildren(
  children: readonly ExpandedXmlVisit[],
  localNames: readonly string[],
): void {
  assertSingletonChildren(children, WORDPROCESSINGML_NAMESPACE, localNames);
}

function assertSingletonChildren(
  children: readonly ExpandedXmlVisit[],
  namespaceUri: string,
  localNames: readonly string[],
): void {
  for (const localName of localNames) {
    if (
      children.filter(
        (child) =>
          child.namespaceUri === namespaceUri && child.localName === localName,
      ).length > 1
    ) {
      failTemplateDocx("XML_INVALID");
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

function resolveReferencedStoryParts(input: {
  document: OrderedXmlNode[];
  documentRelationships: readonly OpcRelationship[];
  contentTypes: ReadonlyMap<string, string>;
}): { headerPartNames: string[]; footerPartNames: string[] } {
  const visits = expandedXmlVisits(input.document);
  assertDocumentSectionTopology(visits);
  const relationshipById = new Map(
    input.documentRelationships.map((relationship) => [
      relationship.id,
      relationship,
    ]),
  );
  const headerPartNames = new Set<string>();
  const footerPartNames = new Set<string>();
  const rolesBySection = new Map<ExpandedXmlVisit, Set<string>>();
  for (const reference of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      ["headerReference", "footerReference"].includes(visit.localName),
  )) {
    if (
      reference.parent?.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      reference.parent.localName !== "sectPr"
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    const id = exactExpandedAttribute(
      reference,
      OFFICE_DOCUMENT_RELATIONSHIPS_NAMESPACE,
      "id",
    );
    const type = exactExpandedAttribute(
      reference,
      WORDPROCESSINGML_NAMESPACE,
      "type",
    );
    if (!id || !type || !["default", "even", "first"].includes(type)) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    const section = reference.parent!;
    const roles = rolesBySection.get(section) ?? new Set<string>();
    const role = `${reference.localName}\0${type}`;
    if (roles.has(role)) failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    roles.add(role);
    rolesBySection.set(section, roles);
    const relationship = relationshipById.get(id);
    const expectedType =
      reference.localName === "headerReference"
        ? HEADER_RELATIONSHIP
        : FOOTER_RELATIONSHIP;
    if (!relationship || relationship.type !== expectedType) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    const targetSet =
      reference.localName === "headerReference"
        ? headerPartNames
        : footerPartNames;
    targetSet.add(relationship.targetPartName);
  }

  const relatedStoryRelationships = input.documentRelationships.filter(
    (relationship) =>
      relationship.type === HEADER_RELATIONSHIP ||
      relationship.type === FOOTER_RELATIONSHIP,
  );
  if (
    relatedStoryRelationships.some((relationship) =>
      relationship.type === HEADER_RELATIONSHIP
        ? !headerPartNames.has(relationship.targetPartName)
        : !footerPartNames.has(relationship.targetPartName),
    )
  ) {
    failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  }

  for (const [partName, contentType] of input.contentTypes) {
    if (
      contentType === DOCX_HEADER_CONTENT_TYPE &&
      !headerPartNames.has(partName)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
    if (
      contentType === DOCX_FOOTER_CONTENT_TYPE &&
      !footerPartNames.has(partName)
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
  }
  return {
    headerPartNames: [...headerPartNames].sort((left, right) =>
      left.localeCompare(right),
    ),
    footerPartNames: [...footerPartNames].sort((left, right) =>
      left.localeCompare(right),
    ),
  };
}

function assertDocumentSectionTopology(
  visits: readonly ExpandedXmlVisit[],
): void {
  const roots = visits.filter((visit) => visit.depth === 0);
  if (
    roots.length !== 1 ||
    roots[0]!.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
    roots[0]!.localName !== "document"
  ) {
    failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  }
  const document = roots[0]!;
  const bodies = visits.filter(
    (visit) =>
      visit.parent === document &&
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "body",
  );
  if (bodies.length !== 1) failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  const body = bodies[0]!;
  const bodyChildren = visits.filter((visit) => visit.parent === body);
  const bodySections = bodyChildren.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "sectPr",
  );
  if (
    bodySections.length > 1 ||
    (bodySections.length === 1 && bodyChildren.at(-1) !== bodySections[0])
  ) {
    failTemplateDocx("OPC_RELATIONSHIP_INVALID");
  }

  const sections = visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "sectPr",
  );
  for (const section of sections) {
    const bodyLevel = section.parent === body;
    const paragraphLevel =
      section.parent?.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      section.parent.localName === "pPr" &&
      section.parent.parent?.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      section.parent.parent.localName === "p";
    if (!bodyLevel && !paragraphLevel) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
  }
  for (const paragraphProperties of visits.filter(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "pPr",
  )) {
    if (
      visits.filter(
        (visit) =>
          visit.parent === paragraphProperties &&
          visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          visit.localName === "sectPr",
      ).length > 1
    ) {
      failTemplateDocx("OPC_RELATIONSHIP_INVALID");
    }
  }
}
