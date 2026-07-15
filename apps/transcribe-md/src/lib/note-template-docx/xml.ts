import { XMLParser } from "fast-xml-parser";

import { failTemplateDocx, TemplateDocxError } from "./errors";
import type { TemplateDocxLimits } from "./limits";

export type OrderedXmlNode = Record<string, unknown> & {
  ":@"?: Record<string, string>;
};

export const OPC_CONTENT_TYPES_NAMESPACE =
  "http://schemas.openxmlformats.org/package/2006/content-types";
export const OPC_RELATIONSHIPS_NAMESPACE =
  "http://schemas.openxmlformats.org/package/2006/relationships";
export const WORDPROCESSINGML_NAMESPACE =
  "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
export const WORDPROCESSINGML_2010_NAMESPACE =
  "http://schemas.microsoft.com/office/word/2010/wordml";
export const WORDPROCESSINGML_2012_NAMESPACE =
  "http://schemas.microsoft.com/office/word/2012/wordml";
export const MARKUP_COMPATIBILITY_NAMESPACE =
  "http://schemas.openxmlformats.org/markup-compatibility/2006";

export interface ExpandedXmlAttribute {
  readonly qualifiedName: string;
  readonly localName: string;
  readonly namespaceUri: string | null;
  readonly value: string;
}

export interface ExpandedXmlVisit {
  readonly node: OrderedXmlNode;
  readonly qualifiedName: string;
  readonly localName: string;
  readonly namespaceUri: string | null;
  readonly attributes: readonly ExpandedXmlAttribute[];
  readonly depth: number;
  readonly parent: ExpandedXmlVisit | null;
}

const XML_DECLARATION_ATTACK_RE = /<!\s*(?:DOCTYPE|ENTITY)\b/i;
const XML_HIDDEN_CONTENT_RE = /<!--|<!\[CDATA\[|<\?/i;

export function parseOrderedXml(
  bytes: Uint8Array,
  limits: TemplateDocxLimits,
): OrderedXmlNode[] {
  if (bytes.byteLength > limits.maxXmlBytes) {
    failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
  }

  let xml: string;
  try {
    xml = decodeXml(bytes);
  } catch (cause) {
    throw new TemplateDocxError("XML_INVALID", { cause });
  }
  if (XML_DECLARATION_ATTACK_RE.test(xml)) failTemplateDocx("XML_DTD_REJECTED");
  const withoutXmlDeclaration = xml.replace(
    /^\uFEFF?\s*<\?xml\b[^?]*\?>/i,
    "",
  );
  if (XML_HIDDEN_CONTENT_RE.test(withoutXmlDeclaration)) {
    failTemplateDocx("XML_HIDDEN_CONTENT_UNSUPPORTED");
  }

  try {
    const parser = new XMLParser({
      preserveOrder: true,
      ignoreAttributes: false,
      attributeNamePrefix: "@_",
      trimValues: false,
      parseTagValue: false,
      parseAttributeValue: false,
      processEntities: false,
      htmlEntities: false,
      maxNestedTags: limits.maxXmlDepth,
    });
    const parsed = parser.parse(xml, true) as unknown;
    if (!Array.isArray(parsed)) failTemplateDocx("XML_INVALID");
    const ordered = parsed as OrderedXmlNode[];
    enforceParsedTreeLimits(ordered, limits);
    return ordered;
  } catch (cause) {
    if (cause instanceof TemplateDocxError) throw cause;
    if (
      cause instanceof Error &&
      /maximum nested tags exceeded/i.test(cause.message)
    ) {
      failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
    }
    throw new TemplateDocxError("XML_INVALID", { cause });
  }
}

function enforceParsedTreeLimits(
  roots: OrderedXmlNode[],
  limits: TemplateDocxLimits,
): void {
  let elementCount = 0;
  let attributeCount = 0;
  let attributeCharacters = 0;
  let textCharacters = 0;
  const stack = roots.map((node) => ({ node, depth: 1 }));
  while (stack.length > 0) {
    const { node, depth } = stack.pop()!;
    const tag = tagOf(node);
    if (tag === "#text") {
      textCharacters += String(node[tag] ?? "").length;
      if (textCharacters > limits.maxXmlTextCharacters) {
        failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
      }
      continue;
    }
    if (tag && tag !== "?xml") {
      elementCount += 1;
      attributeCount += Object.keys(node[":@"] ?? {}).length;
      attributeCharacters += Object.values(node[":@"] ?? {}).reduce(
        (total, value) => total + String(value).length,
        0,
      );
      if (
        elementCount > limits.maxXmlElements ||
        attributeCount > limits.maxXmlAttributes ||
        attributeCharacters > limits.maxXmlAttributeCharacters ||
        depth > limits.maxXmlDepth
      ) {
        failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
      }
    }
    for (const child of childrenOf(node)) {
      stack.push({ node: child, depth: depth + 1 });
    }
  }
}

/**
 * Resolves element and attribute names by namespace URI. Default namespaces
 * apply to elements only; OPC attributes are intentionally unqualified.
 */
export function expandedXmlVisits(
  roots: OrderedXmlNode[],
): ExpandedXmlVisit[] {
  const output: ExpandedXmlVisit[] = [];
  const walk = (
    nodes: OrderedXmlNode[],
    inherited: ReadonlyMap<string, string>,
    depth: number,
    parent: ExpandedXmlVisit | null,
  ): void => {
    for (const node of nodes) {
      const qualifiedName = tagOf(node);
      if (!qualifiedName || qualifiedName === "#text" || qualifiedName === "?xml") {
        continue;
      }
      const namespaces = new Map(inherited);
      for (const [rawName, rawValue] of Object.entries(node[":@"] ?? {})) {
        const name = rawName.startsWith("@_") ? rawName.slice(2) : rawName;
        if (name === "xmlns") namespaces.set("", decodeXmlScalar(String(rawValue)));
        else if (name.startsWith("xmlns:")) {
          namespaces.set(
            name.slice("xmlns:".length),
            decodeXmlScalar(String(rawValue)),
          );
        }
      }
      const elementPrefix = prefixOf(qualifiedName);
      const namespaceUri = namespaces.get(elementPrefix ?? "") ?? null;
      const attributes: ExpandedXmlAttribute[] = [];
      for (const [rawName, rawValue] of Object.entries(node[":@"] ?? {})) {
        const name = rawName.startsWith("@_") ? rawName.slice(2) : rawName;
        if (name === "xmlns" || name.startsWith("xmlns:")) continue;
        const prefix = prefixOf(name);
        attributes.push({
          qualifiedName: name,
          localName: localName(name),
          namespaceUri: prefix ? (namespaces.get(prefix) ?? null) : null,
          value: decodeXmlScalar(String(rawValue)),
        });
      }
      const visit: ExpandedXmlVisit = {
        node,
        qualifiedName,
        localName: localName(qualifiedName),
        namespaceUri,
        attributes,
        depth,
        parent,
      };
      output.push(visit);
      walk(childrenOf(node), namespaces, depth + 1, visit);
    }
  };
  walk(roots, new Map(), 0, null);
  return output;
}

export function exactExpandedAttribute(
  visit: ExpandedXmlVisit,
  namespaceUri: string | null,
  wantedLocalName: string,
): string | undefined {
  const collisions = visit.attributes.filter(
    (attribute) => attribute.localName === wantedLocalName,
  );
  if (
    collisions.length !== 1 ||
    collisions[0]!.namespaceUri !== namespaceUri
  ) {
    return undefined;
  }
  return collisions[0]!.value;
}

export function hasExpandedAttributeCollision(
  visit: ExpandedXmlVisit,
  wantedLocalName: string,
): boolean {
  return (
    visit.attributes.filter(
      (attribute) => attribute.localName === wantedLocalName,
    ).length > 1
  );
}

function prefixOf(name: string): string | null {
  const colon = name.indexOf(":");
  return colon < 0 ? null : name.slice(0, colon);
}

function decodeXml(bytes: Uint8Array): string {
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return new TextDecoder("utf-16le", { fatal: true }).decode(bytes);
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return new TextDecoder("utf-16be", { fatal: true }).decode(bytes);
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

export function tagOf(node: OrderedXmlNode): string {
  return Object.keys(node).find((key) => key !== ":@") ?? "";
}

export function localName(name: string): string {
  const colon = name.indexOf(":");
  return colon < 0 ? name : name.slice(colon + 1);
}

export function childrenOf(node: OrderedXmlNode): OrderedXmlNode[] {
  const value = node[tagOf(node)];
  return Array.isArray(value) ? (value as OrderedXmlNode[]) : [];
}

export function directChild(
  node: OrderedXmlNode,
  wantedLocalName: string,
): OrderedXmlNode | undefined {
  return childrenOf(node).find(
    (child) => localName(tagOf(child)) === wantedLocalName,
  );
}

export function directChildren(
  node: OrderedXmlNode,
  wantedLocalName: string,
): OrderedXmlNode[] {
  return childrenOf(node).filter(
    (child) => localName(tagOf(child)) === wantedLocalName,
  );
}

export function descendants(
  nodeOrNodes: OrderedXmlNode | OrderedXmlNode[],
  wantedLocalName: string,
): OrderedXmlNode[] {
  const roots = Array.isArray(nodeOrNodes) ? nodeOrNodes : [nodeOrNodes];
  const matches: OrderedXmlNode[] = [];
  const stack = [...roots].reverse();
  while (stack.length > 0) {
    const node = stack.pop()!;
    if (localName(tagOf(node)) === wantedLocalName) matches.push(node);
    const children = childrenOf(node);
    for (let index = children.length - 1; index >= 0; index -= 1) {
      stack.push(children[index]!);
    }
  }
  return matches;
}

export function getAttribute(
  node: OrderedXmlNode,
  wantedLocalName: string,
): string | undefined {
  const attributes = node[":@"];
  if (!attributes) return undefined;
  for (const [name, value] of Object.entries(attributes)) {
    const withoutPrefix = name.startsWith("@_") ? name.slice(2) : name;
    if (localName(withoutPrefix) === wantedLocalName) return String(value);
  }
  return undefined;
}

export function visibleText(
  nodeOrNodes: OrderedXmlNode | OrderedXmlNode[],
): string {
  const roots = Array.isArray(nodeOrNodes) ? nodeOrNodes : [nodeOrNodes];
  const output: string[] = [];

  const walk = (nodes: OrderedXmlNode[]): void => {
    for (const node of nodes) {
      const local = localName(tagOf(node));
      if (local === "t" || local === "instrText") {
        output.push(textNodeValue(node));
        continue;
      }
      if (local === "tab") {
        output.push("\t");
        continue;
      }
      if (local === "br" || local === "cr") {
        output.push("\n");
        continue;
      }
      walk(childrenOf(node));
    }
  };
  walk(roots);
  return output.join("");
}

function textNodeValue(node: OrderedXmlNode): string {
  const value = node[tagOf(node)];
  if (typeof value === "string") return decodeXmlScalar(value);
  if (!Array.isArray(value)) return "";
  return (value as OrderedXmlNode[])
    .map((child) => {
      const childTag = tagOf(child);
      return childTag === "#text"
        ? decodeXmlScalar(String(child[childTag] ?? ""))
        : "";
    })
    .join("");
}

export function decodeXmlScalar(value: string): string {
  try {
    const decoded = value
      .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) =>
        safeXmlCodePoint(Number.parseInt(hex, 16)),
      )
      .replace(/&#([0-9]+);/g, (_, decimal: string) =>
        safeXmlCodePoint(Number.parseInt(decimal, 10)),
      )
      .replaceAll("&quot;", '"')
      .replaceAll("&apos;", "'")
      .replaceAll("&gt;", ">")
      .replaceAll("&lt;", "<")
      .replaceAll("&amp;", "&");
    if (/&[A-Za-z_:][A-Za-z0-9_.:-]*;/.test(decoded)) {
      failTemplateDocx("XML_INVALID");
    }
    return decoded;
  } catch (cause) {
    if (cause instanceof TemplateDocxError) throw cause;
    throw new TemplateDocxError("XML_INVALID", { cause });
  }
}

function safeXmlCodePoint(codePoint: number): string {
  if (
    !Number.isSafeInteger(codePoint) ||
    codePoint < 1 ||
    codePoint > 0x10ffff ||
    (codePoint >= 0xd800 && codePoint <= 0xdfff) ||
    (codePoint > 0x7f && codePoint < 0xa0)
  ) {
    failTemplateDocx("XML_INVALID");
  }
  return String.fromCodePoint(codePoint);
}
