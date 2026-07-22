import { XMLParser } from "fast-xml-parser";

import { failTemplateDocx, TemplateDocxError } from "./errors";
import type { TemplateDocxLimits } from "./limits";

export type OrderedXmlNode = Record<string, unknown> & {
  ":@"?: Record<string, string>;
};

const XML_DECLARATION_ATTACK_RE = /<!\s*(?:DOCTYPE|ENTITY)\b/i;

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
    return parsed as OrderedXmlNode[];
  } catch (cause) {
    if (cause instanceof TemplateDocxError) throw cause;
    throw new TemplateDocxError("XML_INVALID", { cause });
  }
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
  if (typeof value === "string") return value;
  if (!Array.isArray(value)) return "";
  return (value as OrderedXmlNode[])
    .map((child) => {
      const childTag = tagOf(child);
      return childTag === "#text" ? String(child[childTag] ?? "") : "";
    })
    .join("");
}
