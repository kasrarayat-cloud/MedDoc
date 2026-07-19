import { canonicalSha256 } from "../template-twin/canonical";
import {
  inspectDocxPackage,
  type InspectedDocxPackage,
} from "./package-security";
import {
  MARKUP_COMPATIBILITY_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  WORDPROCESSINGML_2012_NAMESPACE,
  WORDPROCESSINGML_NAMESPACE,
  XML_NAMESPACE,
  decodeXmlScalar,
  exactExpandedAttribute,
  expandedXmlVisits,
  parseOrderedXml,
  tagOf,
  type ExpandedXmlVisit,
  type OrderedXmlNode,
} from "./xml";

export const OFFICE_LAYOUT_INTEGRITY_CONTRACT_VERSION =
  "template-twin-office-layout-integrity/1.0.0" as const;
export const OFFICE_LAYOUT_CANONICALIZER_VERSION =
  "template-twin-office-layout-canonicalizer/1.0.0" as const;

const OFFICE_RELATIONSHIPS_NAMESPACE =
  "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const SHA256 = /^[a-f0-9]{64}$/u;

export type OfficeLayoutRole =
  | "main_document"
  | "header"
  | "footer"
  | "styles"
  | "numbering";

export type OfficeLayoutScope =
  | "paragraph_properties"
  | "run_properties"
  | "table_properties"
  | "table_grid"
  | "row_properties"
  | "cell_properties"
  | "section_properties"
  | "style_definitions"
  | "numbering_definitions";

export interface OfficeLayoutIntegrityRegion {
  readonly logicalRegionId: string;
  readonly role: OfficeLayoutRole;
  readonly scope: OfficeLayoutScope;
  readonly sourcePartCount: number;
  readonly definitionCount: number;
  readonly canonicalDefinitionsSha256: string;
}

export interface OfficeLayoutIntegrityManifest {
  readonly contractVersion: typeof OFFICE_LAYOUT_INTEGRITY_CONTRACT_VERSION;
  readonly canonicalizerVersion: typeof OFFICE_LAYOUT_CANONICALIZER_VERSION;
  readonly syntheticOnly: true;
  readonly docxSha256: string;
  readonly regions: readonly OfficeLayoutIntegrityRegion[];
  readonly aggregateLayoutSha256: string;
}

export interface OfficeLayoutIntegrityComparison {
  readonly canonicalizerVersion: typeof OFFICE_LAYOUT_CANONICALIZER_VERSION;
  readonly matches: boolean;
  readonly missingRegionIds: readonly string[];
  readonly unexpectedRegionIds: readonly string[];
  readonly changedRegionIds: readonly string[];
  readonly comparisonSha256: string;
}

export interface OfficePdfDocumentFacts {
  readonly normalizedWordTokens: readonly string[];
  readonly pageSizesPoints: readonly {
    readonly width: number;
    readonly height: number;
  }[];
}

interface CanonicalContext {
  readonly numberingIds: ReadonlyMap<string, string>;
  readonly abstractNumberingIds: ReadonlyMap<string, string>;
  readonly relationshipIds: ReadonlyMap<string, string>;
}

interface CanonicalXmlNode {
  readonly name: string;
  readonly attributes: readonly {
    readonly name: string;
    readonly value: string;
  }[];
  readonly children: readonly CanonicalXmlNode[];
}

interface ParsedPart {
  readonly visits: readonly ExpandedXmlVisit[];
  readonly directChildren: ReadonlyMap<
    ExpandedXmlVisit,
    readonly ExpandedXmlVisit[]
  >;
}

interface NumberingSemantics {
  readonly numberingIds: ReadonlyMap<string, string>;
  readonly abstractNumberingIds: ReadonlyMap<string, string>;
  readonly definitions: readonly unknown[];
}

const CONTENT_SCOPE_BY_ELEMENT = new Map<string, OfficeLayoutScope>([
  ["pPr", "paragraph_properties"],
  ["rPr", "run_properties"],
  ["tblPr", "table_properties"],
  ["tblGrid", "table_grid"],
  ["trPr", "row_properties"],
  ["tcPr", "cell_properties"],
  ["sectPr", "section_properties"],
]);

const ON_OFF_ELEMENTS = new Set([
  "autoRedefine",
  "b",
  "bCs",
  "cantSplit",
  "caps",
  "contextualSpacing",
  "default",
  "doNotCheckSpelling",
  "emboss",
  "hidden",
  "i",
  "iCs",
  "imprint",
  "keepLines",
  "keepNext",
  "locked",
  "mirrorIndents",
  "noProof",
  "outline",
  "pageBreakBefore",
  "qFormat",
  "rtl",
  "semiHidden",
  "shadow",
  "smallCaps",
  "snapToGrid",
  "specVanish",
  "suppressAutoHyphens",
  "suppressLineNumbers",
  "suppressOverlap",
  "tblHeader",
  "unhideWhenUsed",
  "vanish",
  "webHidden",
  "widowControl",
  "wordWrap",
]);

const NON_CURRENT_PROPERTY_ELEMENTS = new Set([
  "pPrChange",
  "rPrChange",
  "tblPrChange",
  "trPrChange",
  "tcPrChange",
  "sectPrChange",
]);

const LAYOUT_STYLE_CHILDREN = new Set([
  "basedOn",
  "link",
  "pPr",
  "rPr",
  "tblPr",
  "trPr",
  "tcPr",
  "tblStylePr",
]);

function namespaceName(namespaceUri: string | null): string {
  if (namespaceUri === WORDPROCESSINGML_NAMESPACE) return "w";
  if (namespaceUri === WORDPROCESSINGML_2010_NAMESPACE) return "w14";
  if (namespaceUri === WORDPROCESSINGML_2012_NAMESPACE) return "w15";
  if (namespaceUri === OFFICE_RELATIONSHIPS_NAMESPACE) return "r";
  if (namespaceUri === MARKUP_COMPATIBILITY_NAMESPACE) return "mc";
  if (namespaceUri === XML_NAMESPACE) return "xml";
  return namespaceUri ?? "";
}

function expandedName(namespaceUri: string | null, localName: string): string {
  return `{${namespaceName(namespaceUri)}}${localName}`;
}

function parsePart(
  bytes: Uint8Array,
  inspected: InspectedDocxPackage,
): ParsedPart {
  const visits = expandedXmlVisits(parseOrderedXml(bytes, inspected.limits));
  const mutable = new Map<ExpandedXmlVisit, ExpandedXmlVisit[]>();
  for (const visit of visits) {
    if (!visit.parent) continue;
    const siblings = mutable.get(visit.parent) ?? [];
    siblings.push(visit);
    mutable.set(visit.parent, siblings);
  }
  return {
    visits,
    directChildren: new Map(
      [...mutable].map(([parent, children]) => [
        parent,
        Object.freeze(children),
      ]),
    ),
  };
}

function wordAttribute(
  visit: ExpandedXmlVisit,
  localName: string,
): string | undefined {
  return exactExpandedAttribute(visit, WORDPROCESSINGML_NAMESPACE, localName);
}

function canonicalBoolean(value: string | undefined): string {
  if (
    value === undefined ||
    value === "1" ||
    value === "true" ||
    value === "on"
  ) {
    return "true";
  }
  if (value === "0" || value === "false" || value === "off") return "false";
  return value;
}

function canonicalAttributes(
  visit: ExpandedXmlVisit,
  context: CanonicalContext,
): { readonly name: string; readonly value: string }[] {
  const attributes = visit.attributes
    .filter((attribute) => {
      if (
        attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        /^rsid/u.test(attribute.localName)
      ) {
        return false;
      }
      return ![
        "paraId",
        "textId",
        "anchorId",
        "editId",
        "durableId",
        "dateUtc",
      ].includes(attribute.localName);
    })
    .map((attribute) => {
      let value = attribute.value.normalize("NFC");
      if (
        ON_OFF_ELEMENTS.has(visit.localName) &&
        attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        attribute.localName === "val"
      ) {
        value = canonicalBoolean(value);
      }
      if (
        visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        visit.localName === "style" &&
        attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        ["default", "customStyle"].includes(attribute.localName)
      ) {
        value = canonicalBoolean(value);
      }
      if (
        visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        visit.localName === "numId" &&
        attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        attribute.localName === "val"
      ) {
        value = context.numberingIds.get(value) ?? `unresolved-num:${value}`;
      }
      if (
        visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        visit.localName === "abstractNumId" &&
        attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        attribute.localName === "val"
      ) {
        value =
          context.abstractNumberingIds.get(value) ??
          `unresolved-abstract-num:${value}`;
      }
      if (
        attribute.namespaceUri === OFFICE_RELATIONSHIPS_NAMESPACE &&
        attribute.localName === "id"
      ) {
        value =
          context.relationshipIds.get(value) ??
          `unresolved-relationship:${value}`;
      }
      return {
        name: expandedName(attribute.namespaceUri, attribute.localName),
        value,
      };
    });

  if (
    visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    ON_OFF_ELEMENTS.has(visit.localName) &&
    !attributes.some((attribute) => attribute.name === "{w}val")
  ) {
    attributes.push({ name: "{w}val", value: "true" });
  }
  if (
    visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    visit.localName === "pgMar" &&
    !attributes.some((attribute) => attribute.name === "{w}gutter")
  ) {
    attributes.push({ name: "{w}gutter", value: "0" });
  }
  return attributes.sort(
    (left, right) =>
      left.name.localeCompare(right.name) ||
      left.value.localeCompare(right.value),
  );
}

function canonicalNode(
  visit: ExpandedXmlVisit,
  part: ParsedPart,
  context: CanonicalContext,
  includeChild: (
    parent: ExpandedXmlVisit,
    child: ExpandedXmlVisit,
  ) => boolean = () => true,
): CanonicalXmlNode {
  const children = (part.directChildren.get(visit) ?? [])
    .filter(
      (child) =>
        !(
          child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          NON_CURRENT_PROPERTY_ELEMENTS.has(child.localName)
        ) && includeChild(visit, child),
    )
    .map((child) => canonicalNode(child, part, context, includeChild));
  // OOXML property containers and definition registries are order-insensitive.
  // Sorting their expanded-name representation permits namespace-prefix and
  // schema-order rewrites without hiding a property/value mutation. Table-grid
  // column order is an explicit layout sequence and must remain ordered.
  if (
    !(
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "tblGrid"
    )
  ) {
    children.sort((left, right) =>
      JSON.stringify(left).localeCompare(JSON.stringify(right)),
    );
  }
  return {
    name: expandedName(visit.namespaceUri, visit.localName),
    attributes: canonicalAttributes(visit, context),
    children,
  };
}

function emptyContext(): CanonicalContext {
  return {
    numberingIds: new Map(),
    abstractNumberingIds: new Map(),
    relationshipIds: new Map(),
  };
}

function numberingSemantics(
  inspected: InspectedDocxPackage,
): NumberingSemantics {
  const entry = inspected.zip.entries.get("word/numbering.xml");
  if (!entry) {
    return {
      numberingIds: new Map(),
      abstractNumberingIds: new Map(),
      definitions: Object.freeze([]),
    };
  }
  const part = parsePart(entry.bytes, inspected);
  const directNumberingChildren = part.visits.filter(
    (visit) =>
      visit.parent?.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.parent.localName === "numbering" &&
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE,
  );
  const abstractIds = new Map<string, string>();
  const abstractDefinitions: unknown[] = [];
  for (const abstract of directNumberingChildren.filter(
    (visit) => visit.localName === "abstractNum",
  )) {
    const rawId = wordAttribute(abstract, "abstractNumId");
    if (rawId === undefined) continue;
    const canonical = canonicalNode(
      abstract,
      part,
      emptyContext(),
      (_parent, child) =>
        !(
          child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          ["nsid", "tmpl"].includes(child.localName)
        ),
    );
    const withoutIdentity = {
      ...canonical,
      attributes: canonical.attributes.filter(
        (attribute) => attribute.name !== "{w}abstractNumId",
      ),
    };
    const semanticHash = canonicalSha256(withoutIdentity);
    abstractIds.set(rawId, semanticHash);
    abstractDefinitions.push(withoutIdentity);
  }

  const provisionalContext: CanonicalContext = {
    numberingIds: new Map(),
    abstractNumberingIds: abstractIds,
    relationshipIds: new Map(),
  };
  const numberingIds = new Map<string, string>();
  const numberDefinitions: unknown[] = [];
  for (const number of directNumberingChildren.filter(
    (visit) => visit.localName === "num",
  )) {
    const rawId = wordAttribute(number, "numId");
    if (rawId === undefined) continue;
    const canonical = canonicalNode(number, part, provisionalContext);
    const withoutIdentity = {
      ...canonical,
      attributes: canonical.attributes.filter(
        (attribute) => attribute.name !== "{w}numId",
      ),
    };
    const semanticHash = canonicalSha256(withoutIdentity);
    numberingIds.set(rawId, semanticHash);
    numberDefinitions.push(withoutIdentity);
  }

  const pictureDefinitions = directNumberingChildren
    .filter((visit) => visit.localName === "numPicBullet")
    .map((visit) => canonicalNode(visit, part, provisionalContext));
  const definitions = [
    ...new Map(
      abstractDefinitions.map((definition) => [
        canonicalSha256(definition),
        definition,
      ]),
    ).values(),
    ...new Map(
      numberDefinitions.map((definition) => [
        canonicalSha256(definition),
        definition,
      ]),
    ).values(),
    ...pictureDefinitions,
  ].sort((left, right) =>
    JSON.stringify(left).localeCompare(JSON.stringify(right)),
  );
  return {
    numberingIds,
    abstractNumberingIds: abstractIds,
    definitions: Object.freeze(definitions),
  };
}

function styleDefinitions(
  inspected: InspectedDocxPackage,
  context: CanonicalContext,
): readonly unknown[] {
  const entry = inspected.zip.entries.get("word/styles.xml");
  if (!entry) return Object.freeze([]);
  const part = parsePart(entry.bytes, inspected);
  const definitions: unknown[] = [];
  for (const visit of part.visits) {
    if (
      visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      visit.parent?.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      visit.parent.localName !== "styles"
    ) {
      continue;
    }
    if (visit.localName === "docDefaults") {
      definitions.push(canonicalNode(visit, part, context));
      continue;
    }
    if (visit.localName !== "style") continue;
    const canonical = canonicalNode(
      visit,
      part,
      context,
      (parent, child) =>
        parent !== visit ||
        (child.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          LAYOUT_STYLE_CHILDREN.has(child.localName)),
    );
    definitions.push({
      ...canonical,
      attributes: canonical.attributes.filter((attribute) =>
        ["{w}type", "{w}styleId", "{w}default", "{w}customStyle"].includes(
          attribute.name,
        ),
      ),
    });
  }
  return Object.freeze(
    definitions.sort((left, right) =>
      JSON.stringify(left).localeCompare(JSON.stringify(right)),
    ),
  );
}

function relationshipContext(
  inspected: InspectedDocxPackage,
  numbering: NumberingSemantics,
): CanonicalContext {
  const byId = new Map<string, string>();
  for (const relationship of inspected.relationships
    .filter((candidate) => candidate.sourcePartName === inspected.mainPartName)
    .sort(
      (left, right) =>
        left.type.localeCompare(right.type) ||
        left.targetPartName.localeCompare(right.targetPartName),
    )) {
    const targetKind = relationship.type.slice(
      relationship.type.lastIndexOf("/") + 1,
    );
    // Relationship IDs and target filenames are Word-save implementation
    // details. The referenced content/layout is compared independently in its
    // normalized role region, so the property tree retains only relationship
    // semantics here.
    byId.set(relationship.id, targetKind);
  }
  return {
    numberingIds: numbering.numberingIds,
    abstractNumberingIds: numbering.abstractNumberingIds,
    relationshipIds: byId,
  };
}

function propertyDefinitions(
  entries: readonly Uint8Array[],
  inspected: InspectedDocxPackage,
  context: CanonicalContext,
): ReadonlyMap<OfficeLayoutScope, readonly unknown[]> {
  const perPart: Array<Map<OfficeLayoutScope, unknown[]>> = [];
  for (const bytes of entries) {
    const part = parsePart(bytes, inspected);
    const structuralOrdinals = new Map<ExpandedXmlVisit, number>();
    const counts = new Map<string, number>();
    for (const visit of part.visits) {
      if (visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
      const ordinal = counts.get(visit.localName) ?? 0;
      counts.set(visit.localName, ordinal + 1);
      structuralOrdinals.set(visit, ordinal);
    }
    const byScope = new Map<OfficeLayoutScope, unknown[]>();
    for (const visit of part.visits) {
      if (visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
      const scope = CONTENT_SCOPE_BY_ELEMENT.get(visit.localName);
      if (!scope) continue;
      const canonical = canonicalNode(visit, part, context);
      if (
        canonical.attributes.length === 0 &&
        canonical.children.length === 0
      ) {
        continue;
      }
      const ownerPath: string[] = [];
      let owner = visit.parent;
      while (owner) {
        if (
          owner.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
          ["body", "hdr", "ftr", "p", "r", "tbl", "tr", "tc", "sdt"].includes(
            owner.localName,
          )
        ) {
          ownerPath.push(
            `${owner.localName}:${structuralOrdinals.get(owner) ?? 0}`,
          );
        }
        owner = owner.parent;
      }
      ownerPath.reverse();
      const definitions = byScope.get(scope) ?? [];
      definitions.push({ ownerPath, definition: canonical });
      byScope.set(scope, definitions);
    }
    perPart.push(byScope);
  }
  const output = new Map<OfficeLayoutScope, readonly unknown[]>();
  for (const scope of CONTENT_SCOPE_BY_ELEMENT.values()) {
    const normalizedParts = perPart
      .map((part) => part.get(scope) ?? [])
      .sort((left, right) =>
        JSON.stringify(left).localeCompare(JSON.stringify(right)),
      );
    const definitions = normalizedParts.flatMap((part, partOrdinal) =>
      part.map((definition) => ({ partOrdinal, ...(definition as object) })),
    );
    output.set(scope, Object.freeze(definitions));
  }
  return output;
}

function makeRegion(input: {
  readonly role: OfficeLayoutRole;
  readonly scope: OfficeLayoutScope;
  readonly sourcePartCount: number;
  readonly definitions: readonly unknown[];
}): OfficeLayoutIntegrityRegion {
  return Object.freeze({
    logicalRegionId: `${input.role}:${input.scope}`,
    role: input.role,
    scope: input.scope,
    sourcePartCount: input.sourcePartCount,
    definitionCount: input.definitions.length,
    canonicalDefinitionsSha256: canonicalSha256(input.definitions),
  });
}

/**
 * Canonicalizes layout-affecting WordprocessingML independently of ZIP bytes,
 * namespace prefixes, relationship IDs, definition IDs, and property order.
 * It intentionally does not claim rendered/pixel equivalence; desktop Word
 * visual review remains a separate human gate.
 */
export function buildOfficeLayoutIntegrityManifestQa(input: {
  readonly syntheticOnly: true;
  readonly docxBytes: Uint8Array;
}): OfficeLayoutIntegrityManifest {
  if (input.syntheticOnly !== true)
    throw new Error("Synthetic Office QA only.");
  const inspected = inspectDocxPackage(input.docxBytes);
  const numbering = numberingSemantics(inspected);
  const context = relationshipContext(inspected, numbering);
  const main = inspected.zip.entries.get(inspected.mainPartName);
  if (!main) throw new Error("Office layout main part is missing.");
  const roles = [
    {
      role: "main_document" as const,
      entries: [main.bytes],
    },
    {
      role: "header" as const,
      entries: inspected.headerPartNames.map(
        (partName) => inspected.zip.entries.get(partName)!.bytes,
      ),
    },
    {
      role: "footer" as const,
      entries: inspected.footerPartNames.map(
        (partName) => inspected.zip.entries.get(partName)!.bytes,
      ),
    },
  ];
  const regions: OfficeLayoutIntegrityRegion[] = [];
  for (const role of roles) {
    const definitions = propertyDefinitions(role.entries, inspected, context);
    for (const scope of [
      "paragraph_properties",
      "run_properties",
      "table_properties",
      "table_grid",
      "row_properties",
      "cell_properties",
      "section_properties",
    ] as const) {
      regions.push(
        makeRegion({
          role: role.role,
          scope,
          sourcePartCount: role.entries.length,
          definitions: definitions.get(scope) ?? [],
        }),
      );
    }
  }
  regions.push(
    makeRegion({
      role: "styles",
      scope: "style_definitions",
      sourcePartCount: inspected.zip.entries.has("word/styles.xml") ? 1 : 0,
      definitions: styleDefinitions(inspected, context),
    }),
    makeRegion({
      role: "numbering",
      scope: "numbering_definitions",
      sourcePartCount: inspected.zip.entries.has("word/numbering.xml") ? 1 : 0,
      definitions: numbering.definitions,
    }),
  );
  regions.sort((left, right) =>
    left.logicalRegionId.localeCompare(right.logicalRegionId),
  );
  const unsigned = {
    contractVersion: OFFICE_LAYOUT_INTEGRITY_CONTRACT_VERSION,
    canonicalizerVersion: OFFICE_LAYOUT_CANONICALIZER_VERSION,
    syntheticOnly: true as const,
    docxSha256: inspected.sourceSha256,
    regions: Object.freeze(regions),
  };
  return Object.freeze({
    ...unsigned,
    aggregateLayoutSha256: canonicalSha256(
      regions.map((region) => ({
        logicalRegionId: region.logicalRegionId,
        role: region.role,
        scope: region.scope,
        sourcePartCount: region.sourcePartCount,
        definitionCount: region.definitionCount,
        canonicalDefinitionsSha256: region.canonicalDefinitionsSha256,
      })),
    ),
  });
}

export function compareOfficeLayoutIntegrityManifestsQa(
  before: OfficeLayoutIntegrityManifest,
  after: OfficeLayoutIntegrityManifest,
): OfficeLayoutIntegrityComparison {
  if (
    before.contractVersion !== OFFICE_LAYOUT_INTEGRITY_CONTRACT_VERSION ||
    after.contractVersion !== OFFICE_LAYOUT_INTEGRITY_CONTRACT_VERSION ||
    before.canonicalizerVersion !== OFFICE_LAYOUT_CANONICALIZER_VERSION ||
    after.canonicalizerVersion !== OFFICE_LAYOUT_CANONICALIZER_VERSION ||
    !SHA256.test(before.aggregateLayoutSha256) ||
    !SHA256.test(after.aggregateLayoutSha256)
  ) {
    throw new Error("Invalid Office layout-integrity manifest.");
  }
  const beforeById = new Map(
    before.regions.map((region) => [region.logicalRegionId, region]),
  );
  const afterById = new Map(
    after.regions.map((region) => [region.logicalRegionId, region]),
  );
  const missingRegionIds = [...beforeById.keys()]
    .filter((id) => !afterById.has(id))
    .sort();
  const unexpectedRegionIds = [...afterById.keys()]
    .filter((id) => !beforeById.has(id))
    .sort();
  const changedRegionIds = [...beforeById]
    .filter(([id, beforeRegion]) => {
      const afterRegion = afterById.get(id);
      return Boolean(
        afterRegion &&
        (beforeRegion.role !== afterRegion.role ||
          beforeRegion.scope !== afterRegion.scope ||
          beforeRegion.sourcePartCount !== afterRegion.sourcePartCount ||
          beforeRegion.definitionCount !== afterRegion.definitionCount ||
          beforeRegion.canonicalDefinitionsSha256 !==
            afterRegion.canonicalDefinitionsSha256),
      );
    })
    .map(([id]) => id)
    .sort();
  const unsigned = {
    canonicalizerVersion: OFFICE_LAYOUT_CANONICALIZER_VERSION,
    matches:
      missingRegionIds.length === 0 &&
      unexpectedRegionIds.length === 0 &&
      changedRegionIds.length === 0,
    missingRegionIds,
    unexpectedRegionIds,
    changedRegionIds,
  };
  return Object.freeze({
    ...unsigned,
    comparisonSha256: canonicalSha256(unsigned),
  });
}

function decodedText(node: OrderedXmlNode): string {
  const value = node[tagOf(node)];
  if (typeof value === "string") return decodeXmlScalar(value);
  if (!Array.isArray(value)) return "";
  return (value as OrderedXmlNode[])
    .filter((child) => tagOf(child) === "#text")
    .map((child) => decodeXmlScalar(String(child["#text"] ?? "")))
    .join("");
}

export function normalizeOfficePdfWordTokens(value: string): string[] {
  return (
    value
      .normalize("NFKC")
      .toLocaleLowerCase("en-US")
      .match(/[\p{L}\p{N}]+(?:[’'-][\p{L}\p{N}]+)*/gu) ?? []
  );
}

/** Derives semantic tokens and supported page geometry directly from DOCX bytes. */
export function deriveOfficePdfDocumentFactsQa(input: {
  readonly syntheticOnly: true;
  readonly docxBytes: Uint8Array;
}): OfficePdfDocumentFacts {
  if (input.syntheticOnly !== true)
    throw new Error("Synthetic Office QA only.");
  const inspected = inspectDocxPackage(input.docxBytes);
  const mainEntry = inspected.zip.entries.get(inspected.mainPartName);
  if (!mainEntry) throw new Error("Missing Office main part.");
  const mainVisits = expandedXmlVisits(
    parseOrderedXml(mainEntry.bytes, inspected.limits),
  );
  const settingsEntry = inspected.zip.entries.get("word/settings.xml");
  const settingsVisits = settingsEntry
    ? expandedXmlVisits(parseOrderedXml(settingsEntry.bytes, inspected.limits))
    : [];
  const enabled = (visit: ExpandedXmlVisit): boolean => {
    const value = wordAttribute(visit, "val");
    return value === undefined || ["1", "true", "on"].includes(value);
  };
  const firstPageHeadersEnabled = mainVisits.some(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "titlePg" &&
      enabled(visit),
  );
  const evenHeadersEnabled = settingsVisits.some(
    (visit) =>
      visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      visit.localName === "evenAndOddHeaders" &&
      enabled(visit),
  );
  const activeAuxiliaryParts = new Set<string>();
  for (const visit of mainVisits) {
    if (
      visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      !["headerReference", "footerReference"].includes(visit.localName)
    ) {
      continue;
    }
    const type = wordAttribute(visit, "type") ?? "default";
    if (
      (type === "first" && !firstPageHeadersEnabled) ||
      (type === "even" && !evenHeadersEnabled)
    ) {
      continue;
    }
    const relationshipId = exactExpandedAttribute(
      visit,
      OFFICE_RELATIONSHIPS_NAMESPACE,
      "id",
    );
    const relationship = inspected.relationships.find(
      (candidate) =>
        candidate.sourcePartName === inspected.mainPartName &&
        candidate.id === relationshipId,
    );
    if (relationship) activeAuxiliaryParts.add(relationship.targetPartName);
  }
  const partNames = [
    inspected.mainPartName,
    ...[...activeAuxiliaryParts].sort(),
  ];
  const words: string[] = [];
  const pageSizes: Array<{ width: number; height: number }> = [];
  for (const partName of partNames) {
    const entry = inspected.zip.entries.get(partName);
    if (!entry) throw new Error(`Missing Office text part: ${partName}.`);
    for (const visit of expandedXmlVisits(
      parseOrderedXml(entry.bytes, inspected.limits),
    )) {
      if (visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
      if (visit.localName === "t")
        words.push(...normalizeOfficePdfWordTokens(decodedText(visit.node)));
      if (visit.localName !== "pgSz") continue;
      let widthTwips = Number(wordAttribute(visit, "w"));
      let heightTwips = Number(wordAttribute(visit, "h"));
      if (
        wordAttribute(visit, "orient") === "landscape" &&
        widthTwips < heightTwips
      ) {
        [widthTwips, heightTwips] = [heightTwips, widthTwips];
      }
      if (
        Number.isFinite(widthTwips) &&
        widthTwips > 0 &&
        Number.isFinite(heightTwips) &&
        heightTwips > 0
      ) {
        pageSizes.push({ width: widthTwips / 20, height: heightTwips / 20 });
      }
    }
  }
  if (pageSizes.length === 0) pageSizes.push({ width: 612, height: 792 });
  return Object.freeze({
    normalizedWordTokens: Object.freeze(words),
    pageSizesPoints: Object.freeze([
      ...new Map(
        pageSizes.map((size) => [`${size.width}:${size.height}`, size]),
      ).values(),
    ]),
  });
}
