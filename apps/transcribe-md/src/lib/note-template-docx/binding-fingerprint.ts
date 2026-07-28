import { canonicalSha256 } from '../template-twin/canonical';
import type {
  OrdinaryPlaceholderTokenBinding,
  RendererBinding,
} from '../template-twin/ir';
import {
  WORDPROCESSINGML_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  XML_NAMESPACE,
  childrenOf,
  decodeXmlScalar,
  exactExpandedAttribute,
  expandedXmlVisits,
  tagOf,
  type ExpandedXmlVisit,
  type OrderedXmlNode,
} from './xml';

export const TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION =
  'template-docx-certified-binding/2.0.0' as const;
export const TEMPLATE_TWIN_READBACK_CONTRACT_VERSION =
  'template-docx-readback/2.0.0' as const;

export interface IndexedBindingNode {
  readonly node: OrderedXmlNode;
  /** Original qualified-name path retained for renderer patch compatibility. */
  readonly path: string;
  /** Prefix-independent expanded-name path derived from namespace URIs. */
  readonly canonicalPath: string;
  readonly visit: ExpandedXmlVisit;
  readonly parent: IndexedBindingNode | null;
  readonly order: number;
}

export interface IndexedBindingPart {
  readonly roots: OrderedXmlNode[];
  readonly nodes: readonly IndexedBindingNode[];
  readonly byPath: ReadonlyMap<string, IndexedBindingNode>;
  readonly byCanonicalPath: ReadonlyMap<string, IndexedBindingNode>;
  readonly byNode: ReadonlyMap<OrderedXmlNode, IndexedBindingNode>;
}

export interface NativeBindingIdentity {
  readonly sdtId: string | null;
  readonly tag: string | null;
  readonly alias: string | null;
  readonly legacyName: string | null;
}

export interface DerivedOoxmlBindingIdentity {
  readonly bindingType: RendererBinding['bindingType'];
  readonly nativeIdentity: NativeBindingIdentity;
  /** Hash of immutable OOXML control identity, excluding populated values. */
  readonly identitySha256: string;
}

export interface BindingTableLocation {
  readonly tableIndex: number | null;
  readonly rowIndex: number | null;
  readonly cellIndex: number | null;
}

export interface CertifiedBindingFingerprintInput {
  readonly fieldId: string;
  readonly partName: string;
  readonly canonicalPath: string;
  readonly bindingType: RendererBinding['bindingType'];
  readonly bindingProfile?: RendererBinding['bindingProfile'];
  readonly ordinaryPlaceholder?: RendererBinding['ordinaryPlaceholder'];
  readonly bindingOrdinal: number;
  readonly nativeIdentity: NativeBindingIdentity;
  readonly sourceControlSha256: string;
  readonly sourceBindingIdentitySha256: string;
  readonly tableLocation: BindingTableLocation;
  readonly canonicalRepeatAncestorPath: string | null;
}

export function certifiedBindingFingerprintSha256(
  input: CertifiedBindingFingerprintInput,
): string {
  return canonicalSha256({
    contractVersion: TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
    fieldId: input.fieldId,
    partName: input.partName,
    canonicalPath: input.canonicalPath,
    bindingType: input.bindingType,
    ...(input.bindingProfile === undefined
      ? {}
      : { bindingProfile: input.bindingProfile }),
    ...(input.ordinaryPlaceholder === undefined
      ? {}
      : { ordinaryPlaceholder: input.ordinaryPlaceholder }),
    bindingOrdinal: input.bindingOrdinal,
    nativeIdentity: input.nativeIdentity,
    sourceControlSha256: input.sourceControlSha256,
    sourceBindingIdentitySha256: input.sourceBindingIdentitySha256,
    tableLocation: input.tableLocation,
    canonicalRepeatAncestorPath: input.canonicalRepeatAncestorPath,
  });
}

export function rendererBindingFingerprintSha256(
  fieldId: string,
  binding: Omit<RendererBinding, 'certifiedBindingSha256'>,
): string {
  return certifiedBindingFingerprintSha256({
    fieldId,
    partName: binding.partName,
    canonicalPath: binding.canonicalPath,
    bindingType: binding.bindingType,
    bindingProfile: binding.bindingProfile,
    ordinaryPlaceholder: binding.ordinaryPlaceholder,
    bindingOrdinal: binding.ordinal,
    nativeIdentity: nativeIdentityFromRendererBinding(binding),
    sourceControlSha256: binding.sourceControlSha256,
    sourceBindingIdentitySha256: binding.sourceBindingIdentitySha256,
    tableLocation: {
      tableIndex: binding.tableIndex,
      rowIndex: binding.rowIndex,
      cellIndex: binding.cellIndex,
    },
    canonicalRepeatAncestorPath: binding.canonicalRepeatAncestorPath,
  });
}

export function nativeIdentityFromRendererBinding(
  binding: Pick<RendererBinding, 'sdtId' | 'tag' | 'alias' | 'legacyName'>,
): NativeBindingIdentity {
  return {
    sdtId: binding.sdtId,
    tag: binding.tag,
    alias: binding.alias,
    legacyName: binding.legacyName,
  };
}

export function indexBindingXmlPart(
  roots: OrderedXmlNode[],
): IndexedBindingPart {
  const visits = new Map(
    expandedXmlVisits(roots).map((visit) => [visit.node, visit]),
  );
  const nodes: IndexedBindingNode[] = [];
  const byPath = new Map<string, IndexedBindingNode>();
  const byCanonicalPath = new Map<string, IndexedBindingNode>();
  const byNode = new Map<OrderedXmlNode, IndexedBindingNode>();
  const walk = (
    children: OrderedXmlNode[],
    parentPath: string,
    parentCanonicalPath: string,
    parent: IndexedBindingNode | null,
  ): void => {
    const qualifiedCounts = new Map<string, number>();
    let elementSiblingPosition = 0;
    for (const node of children) {
      const tag = tagOf(node);
      if (!tag || tag === '#text' || tag === '?xml') continue;
      const visit = visits.get(node);
      if (!visit)
        throw new Error('Expanded XML visit missing for binding node.');
      const qualifiedOrdinal = qualifiedCounts.get(tag) ?? 0;
      qualifiedCounts.set(tag, qualifiedOrdinal + 1);
      const path = `${parentPath}/${tag}[${qualifiedOrdinal}]`;
      const canonicalPath =
        `${parentCanonicalPath}/${canonicalExpandedName(visit)}` +
        `[${elementSiblingPosition}]`;
      elementSiblingPosition += 1;
      if (byPath.has(path) || byCanonicalPath.has(canonicalPath)) {
        throw new Error('Duplicate canonical OOXML binding path.');
      }
      const indexed: IndexedBindingNode = {
        node,
        path,
        canonicalPath,
        visit,
        parent,
        order: nodes.length,
      };
      nodes.push(indexed);
      byPath.set(path, indexed);
      byCanonicalPath.set(canonicalPath, indexed);
      byNode.set(node, indexed);
      walk(childrenOf(node), path, canonicalPath, indexed);
    }
  };
  walk(roots, '', '', null);
  return { roots, nodes, byPath, byCanonicalPath, byNode };
}

export function deriveOoxmlBindingIdentity(
  part: IndexedBindingPart,
  bound: IndexedBindingNode,
  bindingType: RendererBinding['bindingType'],
  ordinaryPlaceholder?: OrdinaryPlaceholderTokenBinding,
  ordinaryPlaceholderMode: 'source' | 'output' = 'source',
): DerivedOoxmlBindingIdentity | null {
  if (bindingType === 'content_control') {
    if (!isWordElement(bound, 'sdt')) return null;
    const properties = directWordChild(part, bound, 'sdtPr');
    if (!properties) return null;
    const nativeIdentity: NativeBindingIdentity = {
      sdtId: boundedIdentity(
        wordAttribute(directWordChild(part, properties, 'id'), 'val'),
        80,
      ),
      tag: boundedIdentity(
        wordAttribute(directWordChild(part, properties, 'tag'), 'val'),
        240,
      ),
      alias: boundedIdentity(
        wordAttribute(directWordChild(part, properties, 'alias'), 'val'),
        240,
      ),
      legacyName: null,
    };
    const descriptor = contentControlDescriptor(
      part,
      properties,
      nativeIdentity,
    );
    return {
      bindingType,
      nativeIdentity,
      identitySha256: canonicalSha256(descriptor),
    };
  }

  if (bindingType === 'legacy_form_field') {
    if (!isWordElement(bound, 'fldChar')) return null;
    const formData = descendantsWord(part, bound, 'ffData')[0];
    if (!formData) return null;
    const name = descendantsWord(part, formData, 'name')[0];
    const nativeIdentity: NativeBindingIdentity = {
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: boundedIdentity(wordAttribute(name, 'val'), 240),
    };
    return {
      bindingType,
      nativeIdentity,
      identitySha256: canonicalSha256(
        legacyControlDescriptor(part, formData, nativeIdentity),
      ),
    };
  }

  if (bindingType === 'table_cell') {
    if (!isWordElement(bound, 'tc')) return null;
    return {
      bindingType,
      nativeIdentity: emptyNativeIdentity(),
      identitySha256: canonicalSha256(tableCellDescriptor(part, bound)),
    };
  }

  if (bindingType === 'ordinary_placeholder') {
    if (!ordinaryPlaceholder || !isWordElement(bound, 'p')) return null;
    const descriptor = deriveOrdinaryPlaceholderBinding(
      part,
      bound,
      ordinaryPlaceholder,
      ordinaryPlaceholderMode,
    );
    if (!descriptor) return null;
    return {
      bindingType,
      nativeIdentity: emptyNativeIdentity(),
      identitySha256: descriptor.identitySha256,
    };
  }

  // Complex repeating structures remain certification-blocked in safe alpha.
  return null;
}

export interface DerivedOrdinaryPlaceholderBinding {
  readonly identitySha256: string;
  /** Output-observable slot identity. Unlike the certified identity this
   * deliberately excludes source-token text/syntax, which no longer exists
   * after a legitimate replacement. It is used only for the package-wide
   * duplicate census; exact certified path/identity is still checked
   * separately for every field. */
  readonly outputCensusSha256: string;
  /** Source token in source mode; populated clinical value in output mode. */
  readonly mutableValue: string;
}

/**
 * Independently derives the placeholder slot from parsed OOXML. The immutable
 * descriptor supplies only certified offsets and hashes; every structural
 * node, static character, and output value is read from the provided part.
 */
export function deriveOrdinaryPlaceholderBinding(
  part: IndexedBindingPart,
  paragraph: IndexedBindingNode,
  binding: OrdinaryPlaceholderTokenBinding,
  mode: 'source' | 'output',
): DerivedOrdinaryPlaceholderBinding | null {
  if (!isWordElement(paragraph, 'p')) return null;
  const textNodes = ordinaryPlaceholderTextNodes(part, paragraph);
  if (!textNodes || textNodes.length !== binding.span.paragraphTextNodeCount) {
    return null;
  }
  const values = textNodes.map((node) => wordTextNodeValue(node));
  if (
    mode === 'output' &&
    textNodes.some((node, index) => {
      const value = values[index] ?? '';
      const requiresPreservation = /^[\t\r\n ]|[\t\r\n ]$/u.test(value);
      if (!requiresPreservation) return false;
      return !node.visit.attributes.some(
        (attribute) =>
          attribute.namespaceUri === XML_NAMESPACE &&
          attribute.localName === 'space' &&
          attribute.value === 'preserve',
      );
    })
  ) {
    return null;
  }
  const startIndex = binding.span.startTextNodeIndex;
  const endIndex = binding.span.endTextNodeIndex;
  const start = values[startIndex];
  const end = values[endIndex];
  if (start === undefined || end === undefined) return null;

  let mutableValue: string;
  let prefix: string;
  let suffix: string;
  const normalized = [...values];
  if (mode === 'source') {
    if (
      binding.span.startOffset > start.length ||
      binding.span.endOffset > end.length ||
      (startIndex === endIndex &&
        binding.span.endOffset <= binding.span.startOffset)
    ) {
      return null;
    }
    prefix = start.slice(0, binding.span.startOffset);
    suffix = end.slice(binding.span.endOffset);
    mutableValue =
      startIndex === endIndex
        ? start.slice(binding.span.startOffset, binding.span.endOffset)
        : [
            start.slice(binding.span.startOffset),
            ...values.slice(startIndex + 1, endIndex),
            end.slice(0, binding.span.endOffset),
          ].join('');
  } else {
    if (
      start.length < binding.staticPrefixLength ||
      end.length < binding.staticSuffixLength
    ) {
      return null;
    }
    prefix = start.slice(0, binding.staticPrefixLength);
    suffix = binding.staticSuffixLength
      ? end.slice(-binding.staticSuffixLength)
      : '';
    if (startIndex === endIndex) {
      if (
        start.length <
        binding.staticPrefixLength + binding.staticSuffixLength
      ) {
        return null;
      }
      mutableValue = start.slice(
        binding.staticPrefixLength,
        binding.staticSuffixLength
          ? start.length - binding.staticSuffixLength
          : start.length,
      );
    } else {
      if (
        values.slice(startIndex + 1, endIndex).some((value) => value !== '')
      ) {
        return null;
      }
      const lastMutableEnd = binding.staticSuffixLength
        ? end.length - binding.staticSuffixLength
        : end.length;
      if (lastMutableEnd !== 0) return null;
      mutableValue = start.slice(binding.staticPrefixLength);
    }
  }

  if (
    prefix.length !== binding.staticPrefixLength ||
    suffix.length !== binding.staticSuffixLength ||
    canonicalSha256(prefix) !== binding.staticPrefixSha256 ||
    canonicalSha256(suffix) !== binding.staticSuffixSha256 ||
    canonicalSha256({ prefix, suffix }) !== binding.staticContextSha256
  ) {
    return null;
  }
  if (
    mode === 'source' &&
    (mutableValue.length !== binding.tokenTextLength ||
      canonicalSha256(mutableValue) !== binding.tokenTextSha256 ||
      ordinaryPlaceholderSyntax(mutableValue) !== binding.tokenSyntax)
  ) {
    return null;
  }

  normalized[startIndex] = `${prefix}\u0000TEMPLATE_TWIN_MUTABLE\u0000`;
  for (let index = startIndex + 1; index < endIndex; index += 1) {
    normalized[index] = '';
  }
  if (startIndex === endIndex) {
    normalized[startIndex] =
      `${prefix}\u0000TEMPLATE_TWIN_MUTABLE\u0000${suffix}`;
  } else {
    normalized[endIndex] = suffix;
  }
  const shapeSha256 = canonicalSha256(
    ordinaryPlaceholderShapeDescriptor(part, paragraph, textNodes, normalized),
  );
  if (shapeSha256 !== binding.sourceParagraphShapeSha256) return null;
  return {
    mutableValue,
    outputCensusSha256: canonicalSha256({
      bindingType: 'ordinary_placeholder',
      bindingProfile: 'ORDINARY_PLACEHOLDER_TOKEN_V1',
      paragraphTextNodeCount: binding.span.paragraphTextNodeCount,
      startTextNodeIndex: binding.span.startTextNodeIndex,
      endTextNodeIndex: binding.span.endTextNodeIndex,
      staticPrefixLength: binding.staticPrefixLength,
      staticSuffixLength: binding.staticSuffixLength,
      staticPrefixSha256: binding.staticPrefixSha256,
      staticSuffixSha256: binding.staticSuffixSha256,
      staticContextSha256: binding.staticContextSha256,
      sourceParagraphShapeSha256: shapeSha256,
    }),
    identitySha256: canonicalSha256({
      bindingType: 'ordinary_placeholder',
      bindingProfile: 'ORDINARY_PLACEHOLDER_TOKEN_V1',
      tokenSyntax: binding.tokenSyntax,
      tokenTextSha256: binding.tokenTextSha256,
      tokenTextLength: binding.tokenTextLength,
      span: binding.span,
      staticPrefixSha256: binding.staticPrefixSha256,
      staticSuffixSha256: binding.staticSuffixSha256,
      staticContextSha256: binding.staticContextSha256,
      sourceParagraphShapeSha256: shapeSha256,
    }),
  };
}

export function ordinaryPlaceholderSyntax(
  token: string,
): OrdinaryPlaceholderTokenBinding['tokenSyntax'] | null {
  if (/^<<[^<>\r\n]{1,160}>>$/u.test(token)) return 'angle';
  if (/^\[\[[^\[\]\r\n]{1,160}\]\]$/u.test(token)) return 'square';
  if (/^\{\{[^{}\r\n]{1,160}\}\}$/u.test(token)) return 'curly';
  if (/^_{3,160}$/u.test(token)) return 'underscore';
  return null;
}

export function certifyOrdinaryPlaceholderTokenBinding(input: {
  part: IndexedBindingPart;
  paragraph: IndexedBindingNode;
  startTextNodeIndex: number;
  startOffset: number;
  endTextNodeIndex: number;
  endOffset: number;
}): OrdinaryPlaceholderTokenBinding | null {
  const textNodes = ordinaryPlaceholderTextNodes(input.part, input.paragraph);
  if (!textNodes) return null;
  const values = textNodes.map((node) => wordTextNodeValue(node));
  const start = values[input.startTextNodeIndex];
  const end = values[input.endTextNodeIndex];
  if (
    start === undefined ||
    end === undefined ||
    input.endTextNodeIndex < input.startTextNodeIndex ||
    input.startOffset > start.length ||
    input.endOffset > end.length ||
    (input.startTextNodeIndex === input.endTextNodeIndex &&
      input.endOffset <= input.startOffset)
  ) {
    return null;
  }
  const prefix = start.slice(0, input.startOffset);
  const suffix = end.slice(input.endOffset);
  const token =
    input.startTextNodeIndex === input.endTextNodeIndex
      ? start.slice(input.startOffset, input.endOffset)
      : [
          start.slice(input.startOffset),
          ...values.slice(input.startTextNodeIndex + 1, input.endTextNodeIndex),
          end.slice(0, input.endOffset),
        ].join('');
  const tokenSyntax = ordinaryPlaceholderSyntax(token);
  if (!tokenSyntax) return null;
  const normalized = [...values];
  normalized[input.startTextNodeIndex] =
    `${prefix}\u0000TEMPLATE_TWIN_MUTABLE\u0000`;
  for (
    let index = input.startTextNodeIndex + 1;
    index < input.endTextNodeIndex;
    index += 1
  ) {
    normalized[index] = '';
  }
  if (input.startTextNodeIndex === input.endTextNodeIndex) {
    normalized[input.startTextNodeIndex] =
      `${prefix}\u0000TEMPLATE_TWIN_MUTABLE\u0000${suffix}`;
  } else {
    normalized[input.endTextNodeIndex] = suffix;
  }
  return {
    contractVersion: 'ordinary-placeholder-token-binding/1.0.0',
    tokenSyntax,
    tokenTextSha256: canonicalSha256(token),
    tokenTextLength: token.length,
    span: {
      startTextNodeIndex: input.startTextNodeIndex,
      startOffset: input.startOffset,
      endTextNodeIndex: input.endTextNodeIndex,
      endOffset: input.endOffset,
      paragraphTextNodeCount: textNodes.length,
    },
    staticPrefixLength: prefix.length,
    staticSuffixLength: suffix.length,
    staticPrefixSha256: canonicalSha256(prefix),
    staticSuffixSha256: canonicalSha256(suffix),
    staticContextSha256: canonicalSha256({ prefix, suffix }),
    sourceParagraphShapeSha256: canonicalSha256(
      ordinaryPlaceholderShapeDescriptor(
        input.part,
        input.paragraph,
        textNodes,
        normalized,
      ),
    ),
    clinicalMappingStatus: 'needs_confirmation',
  };
}

function ordinaryPlaceholderTextNodes(
  part: IndexedBindingPart,
  paragraph: IndexedBindingNode,
): IndexedBindingNode[] | null {
  const paragraphChildren = elementChildren(part, paragraph);
  if (
    paragraphChildren.some(
      (child) => !isWordElement(child, 'pPr') && !isWordElement(child, 'r'),
    ) ||
    paragraphChildren.filter((child) => isWordElement(child, 'pPr')).length > 1
  ) {
    return null;
  }
  const runs = paragraphChildren.filter((child) => isWordElement(child, 'r'));
  if (runs.length === 0) return null;
  const textNodes: IndexedBindingNode[] = [];
  for (const run of runs) {
    const runChildren = elementChildren(part, run);
    if (
      runChildren.some(
        (child) => !isWordElement(child, 'rPr') && !isWordElement(child, 't'),
      ) ||
      runChildren.filter((child) => isWordElement(child, 'rPr')).length > 1
    ) {
      return null;
    }
    const texts = runChildren.filter((child) => isWordElement(child, 't'));
    if (texts.length === 0) return null;
    for (const text of texts) {
      if (elementChildren(part, text).length > 0) return null;
      if (
        text.visit.attributes.some(
          (attribute) =>
            attribute.namespaceUri !== XML_NAMESPACE ||
            attribute.localName !== 'space' ||
            attribute.value !== 'preserve',
        ) ||
        text.visit.attributes.length > 1
      ) {
        return null;
      }
      textNodes.push(text);
    }
  }
  const allowedCharacterParents = new Set(textNodes.map((text) => text.node));
  const stack = [paragraph.node];
  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const child of childrenOf(current)) {
      if (tagOf(child) === '#text') {
        if (
          !allowedCharacterParents.has(current) &&
          !/^\s*$/u.test(String(child['#text'] ?? ''))
        ) {
          return null;
        }
        continue;
      }
      stack.push(child);
    }
  }
  return textNodes;
}

function wordTextNodeValue(node: IndexedBindingNode): string {
  return childrenOf(node.node)
    .filter((child) => tagOf(child) === '#text')
    .map((child) => decodeXmlScalar(String(child['#text'] ?? '')))
    .join('');
}

function ordinaryPlaceholderShapeDescriptor(
  part: IndexedBindingPart,
  paragraph: IndexedBindingNode,
  textNodes: readonly IndexedBindingNode[],
  normalizedValues: readonly string[],
): unknown {
  const normalizedByNode = new Map(
    textNodes.map((node, index) => [node, normalizedValues[index] ?? '']),
  );
  const describe = (node: IndexedBindingNode): unknown => {
    const replacement = normalizedByNode.get(node);
    const children = childrenOf(node.node).flatMap((child) => {
      if (tagOf(child) === '#text') {
        if (replacement !== undefined) return [];
        const value = decodeXmlScalar(String(child['#text'] ?? ''));
        return /^\s*$/u.test(value)
          ? []
          : [{ namespaceUri: null, localName: '#text', value }];
      }
      const indexed = part.byNode.get(child);
      return indexed ? [describe(indexed)] : [];
    });
    if (replacement !== undefined) {
      children.push({
        namespaceUri: null,
        localName: '#text',
        value: replacement,
      });
    }
    return {
      namespaceUri: node.visit.namespaceUri,
      localName: node.visit.localName,
      // The renderer may need to add xml:space="preserve" after removing a
      // token exposes certified static boundary whitespace. The actual text
      // node is validated above; omitting only that presentation attribute
      // from the normalized slot shape keeps source and output identities
      // stable without allowing any other attribute mutation.
      attributes:
        replacement === undefined ? immutableAttributeDescriptor(node) : [],
      children,
    };
  };
  return describe(paragraph);
}

/**
 * Derives the narrow compatibility profile from the completed OOXML itself.
 * This is intentionally stricter than a visible-text test: paragraph tab-stop
 * properties are immutable layout, while the only mutable output slot is one
 * direct plain-text run following w:pPr. A blank certified source has no run.
 */
export function deriveTableCellBindingProfile(
  part: IndexedBindingPart,
  bound: IndexedBindingNode,
): RendererBinding['bindingProfile'] | null {
  if (!isWordElement(bound, 'tc') || bound.visit.attributes.length > 0) {
    return null;
  }
  const cellChildren = elementChildren(part, bound);
  const paragraphs = directWordChildren(part, bound, 'p');
  if (
    paragraphs.length !== 1 ||
    cellChildren.some(
      (child) => !isWordElement(child, 'tcPr') && !isWordElement(child, 'p'),
    ) ||
    cellChildren.filter((child) => isWordElement(child, 'p')).length !== 1 ||
    cellChildren.filter((child) => isWordElement(child, 'tcPr')).length > 1
  ) {
    return null;
  }
  const cellProperties = directWordChild(part, bound, 'tcPr');
  if (
    cellProperties &&
    (descendantsWord(part, cellProperties, 'vMerge').length > 0 ||
      descendantsWord(part, cellProperties, 'gridSpan').some(
        (span) => wordAttribute(span, 'val') !== '1',
      ))
  ) {
    return null;
  }

  const paragraph = paragraphs[0]!;
  if (!validProfileParagraphAttributes(paragraph)) return null;
  const paragraphChildren = elementChildren(part, paragraph);
  const paragraphProperties = directWordChild(part, paragraph, 'pPr');
  if (
    !paragraphProperties ||
    paragraphProperties.visit.attributes.length > 0 ||
    paragraphChildren[0] !== paragraphProperties
  ) {
    return null;
  }
  const tabSets = directWordChildren(part, paragraphProperties, 'tabs');
  if (tabSets.length !== 1) return null;
  const tabSetChildren = elementChildren(part, tabSets[0]!);
  if (
    tabSetChildren.length === 0 ||
    tabSetChildren.some(
      (tab) =>
        !isWordElement(tab, 'tab') ||
        wordAttribute(tab, 'val') !== 'left' ||
        !/^[0-9]+$/.test(wordAttribute(tab, 'pos') ?? ''),
    )
  ) {
    return null;
  }

  const mutableChildren = paragraphChildren.slice(1);
  if (mutableChildren.length === 0) {
    return hasOnlyExpectedCharacterData(bound, null)
      ? 'TAB_ONLY_BLANK_TABLE_CELL_V1'
      : null;
  }
  if (
    mutableChildren.length !== 1 ||
    !isWordElement(mutableChildren[0]!, 'r')
  ) {
    return null;
  }
  const run = mutableChildren[0]!;
  if (run.visit.attributes.length > 0) return null;
  const runChildren = elementChildren(part, run);
  if (runChildren.length !== 1 || !isWordElement(runChildren[0]!, 't')) {
    return null;
  }
  const text = runChildren[0]!;
  if (
    elementChildren(part, text).length > 0 ||
    !validRenderedTextAttributes(text) ||
    !hasOnlyExpectedCharacterData(bound, text)
  ) {
    return null;
  }
  return 'TAB_ONLY_BLANK_TABLE_CELL_V1';
}

function validProfileParagraphAttributes(
  paragraph: IndexedBindingNode,
): boolean {
  const seen = new Set<string>();
  for (const attribute of paragraph.visit.attributes) {
    const key = `${attribute.namespaceUri ?? ''}\0${attribute.localName}`;
    if (seen.has(key)) return false;
    seen.add(key);
    if (attribute.namespaceUri === WORDPROCESSINGML_NAMESPACE) {
      if (
        !['rsidP', 'rsidR', 'rsidRDefault', 'rsidRPr'].includes(
          attribute.localName,
        ) ||
        !/^[0-9A-Fa-f]{8}$/.test(attribute.value)
      ) {
        return false;
      }
      continue;
    }
    if (
      attribute.namespaceUri !== WORDPROCESSINGML_2010_NAMESPACE ||
      !['paraId', 'textId'].includes(attribute.localName) ||
      !/^[0-9A-Fa-f]{8}$/.test(attribute.value)
    ) {
      return false;
    }
  }
  return true;
}

function validRenderedTextAttributes(text: IndexedBindingNode): boolean {
  const rawText = childrenOf(text.node)
    .filter((child) => tagOf(child) === '#text')
    .map((child) => String(child['#text'] ?? ''))
    .join('');
  const requiresPreservation = /^\s|\s$/u.test(rawText);
  if (text.visit.attributes.length === 0) return !requiresPreservation;
  return (
    text.visit.attributes.length === 1 &&
    text.visit.attributes[0]!.namespaceUri === XML_NAMESPACE &&
    text.visit.attributes[0]!.localName === 'space' &&
    text.visit.attributes[0]!.value === 'preserve' &&
    requiresPreservation
  );
}

function hasOnlyExpectedCharacterData(
  bound: IndexedBindingNode,
  mutableText: IndexedBindingNode | null,
): boolean {
  const stack = [bound.node];
  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const child of childrenOf(current)) {
      if (tagOf(child) === '#text') {
        if (
          current !== mutableText?.node &&
          !/^\s*$/u.test(String(child['#text'] ?? ''))
        ) {
          return false;
        }
        continue;
      }
      stack.push(child);
    }
  }
  return true;
}

function elementChildren(
  part: IndexedBindingPart,
  parent: IndexedBindingNode,
): IndexedBindingNode[] {
  return childrenOf(parent.node).flatMap((child) => {
    const indexed = part.byNode.get(child);
    return indexed ? [indexed] : [];
  });
}

function tableCellDescriptor(
  part: IndexedBindingPart,
  cell: IndexedBindingNode,
): unknown {
  const properties = directWordChild(part, cell, 'tcPr');
  const paragraphs = directWordChildren(part, cell, 'p');
  const profile = deriveTableCellBindingProfile(part, cell);
  return {
    bindingType: 'table_cell',
    ...(profile
      ? {
          bindingProfile: profile,
          cellAttributes: immutableAttributeDescriptor(cell),
          paragraphAttributes: paragraphs.map(immutableAttributeDescriptor),
        }
      : {}),
    cellProperties: properties
      ? immutableXmlDescriptor(part, properties)
      : null,
    paragraphProperties: paragraphs.map((paragraph) => {
      const paragraphProperties = directWordChild(part, paragraph, 'pPr');
      return paragraphProperties
        ? immutableXmlDescriptor(part, paragraphProperties)
        : null;
    }),
    paragraphCount: paragraphs.length,
    nestedTableCount: descendantsWord(part, cell, 'tbl').length,
  };
}

function immutableAttributeDescriptor(node: IndexedBindingNode): unknown {
  return [...node.visit.attributes]
    .map((attribute) => ({
      namespaceUri: attribute.namespaceUri,
      localName: attribute.localName,
      value: attribute.value,
    }))
    .sort((left, right) =>
      `${left.namespaceUri ?? ''}\0${left.localName}`.localeCompare(
        `${right.namespaceUri ?? ''}\0${right.localName}`,
      ),
    );
}

function immutableXmlDescriptor(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
): unknown {
  return {
    namespaceUri: node.visit.namespaceUri,
    localName: node.visit.localName,
    attributes: [...node.visit.attributes]
      .map((attribute) => ({
        namespaceUri: attribute.namespaceUri,
        localName: attribute.localName,
        value: attribute.value,
      }))
      .sort((left, right) =>
        `${left.namespaceUri ?? ''}\u0000${left.localName}`.localeCompare(
          `${right.namespaceUri ?? ''}\u0000${right.localName}`,
        ),
      ),
    children: childrenOf(node.node).flatMap((child) => {
      if (tagOf(child) === '#text') {
        const value = String(child['#text'] ?? '');
        return /^\s*$/u.test(value)
          ? []
          : [{ namespaceUri: null, localName: '#text', value }];
      }
      const indexed = part.byNode.get(child);
      return indexed ? [immutableXmlDescriptor(part, indexed)] : [];
    }),
  };
}

export function deriveTableLocation(
  part: IndexedBindingPart,
  bound: IndexedBindingNode,
): BindingTableLocation {
  let cell: IndexedBindingNode | null = bound;
  while (cell && !isWordElement(cell, 'tc')) cell = cell.parent;
  if (!cell) return { tableIndex: null, rowIndex: null, cellIndex: null };
  let row: IndexedBindingNode | null = cell.parent;
  while (row && !isWordElement(row, 'tr')) row = row.parent;
  let table: IndexedBindingNode | null = row?.parent ?? null;
  while (table && !isWordElement(table, 'tbl')) table = table.parent;
  if (!row || !table)
    return { tableIndex: null, rowIndex: null, cellIndex: null };
  return {
    tableIndex: part.nodes
      .filter((node) => isWordElement(node, 'tbl'))
      .indexOf(table),
    rowIndex: directWordChildren(part, table, 'tr').indexOf(row),
    cellIndex: directWordChildren(part, row, 'tc').indexOf(cell),
  };
}

export function hasStrongNativeIdentity(
  identity: NativeBindingIdentity,
): boolean {
  return Boolean(
    identity.sdtId || identity.tag || identity.alias || identity.legacyName,
  );
}

export function sameNativeIdentity(
  left: NativeBindingIdentity,
  right: NativeBindingIdentity,
): boolean {
  return (
    left.sdtId === right.sdtId &&
    left.tag === right.tag &&
    left.alias === right.alias &&
    left.legacyName === right.legacyName
  );
}

function canonicalExpandedName(visit: ExpandedXmlVisit): string {
  return `Q{${encodeURIComponent(visit.namespaceUri ?? '')}}${visit.localName}`;
}

function contentControlDescriptor(
  part: IndexedBindingPart,
  properties: IndexedBindingNode,
  nativeIdentity: NativeBindingIdentity,
): unknown {
  const checkbox = descendants(part, properties).find(
    (node) =>
      node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      node.visit.localName === 'checkbox',
  );
  const date = directWordChild(part, properties, 'date');
  const dropdown = directWordChild(part, properties, 'dropDownList');
  const combo = directWordChild(part, properties, 'comboBox');
  const text = directWordChild(part, properties, 'text');
  const choice = dropdown ?? combo;
  return {
    bindingType: 'content_control',
    nativeIdentity,
    controlType: checkbox
      ? 'checkbox'
      : date
        ? 'date'
        : dropdown
          ? 'dropdown'
          : combo
            ? 'combo'
            : text
              ? 'plain_text'
              : 'rich_or_unknown',
    options: choice
      ? descendantsWord(part, choice, 'listItem').map((item) => ({
          displayText: wordAttribute(item, 'displayText') ?? null,
          value: wordAttribute(item, 'value') ?? null,
        }))
      : [],
    date: date
      ? {
          format:
            wordAttribute(
              descendantsWord(part, date, 'dateFormat')[0],
              'val',
            ) ?? null,
          locale:
            wordAttribute(descendantsWord(part, date, 'lid')[0], 'val') ?? null,
          calendar:
            wordAttribute(descendantsWord(part, date, 'calendar')[0], 'val') ??
            null,
          storage:
            wordAttribute(
              descendantsWord(part, date, 'storeMappedDataAs')[0],
              'val',
            ) ?? null,
        }
      : null,
    checkbox: checkbox
      ? {
          checkedState: stateDescriptor(part, checkbox, 'checkedState'),
          uncheckedState: stateDescriptor(part, checkbox, 'uncheckedState'),
        }
      : null,
    multiline: text ? (wordAttribute(text, 'multiLine') ?? null) : null,
  };
}

function legacyControlDescriptor(
  part: IndexedBindingPart,
  formData: IndexedBindingNode,
  nativeIdentity: NativeBindingIdentity,
): unknown {
  const checkbox = descendantsWord(part, formData, 'checkBox')[0];
  const dropdown = descendantsWord(part, formData, 'ddList')[0];
  const text = descendantsWord(part, formData, 'textInput')[0];
  return {
    bindingType: 'legacy_form_field',
    nativeIdentity,
    controlType: checkbox
      ? 'checkbox'
      : dropdown
        ? 'dropdown'
        : text
          ? 'text'
          : 'unknown',
    options: dropdown
      ? descendantsWord(part, dropdown, 'listEntry').map(
          (entry) => wordAttribute(entry, 'val') ?? null,
        )
      : [],
    text: text
      ? {
          type:
            wordAttribute(descendantsWord(part, text, 'type')[0], 'val') ??
            null,
          format:
            wordAttribute(descendantsWord(part, text, 'format')[0], 'val') ??
            null,
          maxLength:
            wordAttribute(descendantsWord(part, text, 'maxLength')[0], 'val') ??
            null,
        }
      : null,
    checkbox: checkbox
      ? {
          default:
            wordAttribute(
              descendantsWord(part, checkbox, 'default')[0],
              'val',
            ) ?? null,
          size:
            wordAttribute(descendantsWord(part, checkbox, 'size')[0], 'val') ??
            null,
          sizeAuto: descendantsWord(part, checkbox, 'sizeAuto').length === 1,
        }
      : null,
  };
}

function stateDescriptor(
  part: IndexedBindingPart,
  checkbox: IndexedBindingNode,
  localName: string,
): unknown {
  const node = descendants(part, checkbox).find(
    (candidate) =>
      candidate.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      candidate.visit.localName === localName,
  );
  return node
    ? {
        value:
          exactExpandedAttribute(
            node.visit,
            WORDPROCESSINGML_2010_NAMESPACE,
            'val',
          ) ?? null,
        font:
          exactExpandedAttribute(
            node.visit,
            WORDPROCESSINGML_2010_NAMESPACE,
            'font',
          ) ?? null,
      }
    : null;
}

function emptyNativeIdentity(): NativeBindingIdentity {
  return { sdtId: null, tag: null, alias: null, legacyName: null };
}

function boundedIdentity(
  value: string | undefined,
  maximumLength: number,
): string | null {
  const normalized = value?.trim();
  return normalized ? normalized.slice(0, maximumLength) : null;
}

function directWordChild(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode | undefined {
  return childrenOf(node.node)
    .map((child) => part.byNode.get(child))
    .find((child): child is IndexedBindingNode =>
      Boolean(child && isWordElement(child, localName)),
    );
}

function directWordChildren(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  return childrenOf(node.node)
    .map((child) => part.byNode.get(child))
    .filter((child): child is IndexedBindingNode =>
      Boolean(child && isWordElement(child, localName)),
    );
}

function descendantsWord(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  return descendants(part, node).filter(
    (candidate) =>
      candidate.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
      candidate.visit.localName === localName,
  );
}

function descendants(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
): IndexedBindingNode[] {
  const output: IndexedBindingNode[] = [];
  const stack = [...childrenOf(node.node)].reverse();
  while (stack.length > 0) {
    const child = stack.pop()!;
    if (tagOf(child) === '#text' || tagOf(child) === '?xml') continue;
    const indexed = part.byNode.get(child);
    if (!indexed) throw new Error('Indexed OOXML descendant missing.');
    output.push(indexed);
    const grandchildren = childrenOf(child);
    for (let index = grandchildren.length - 1; index >= 0; index -= 1) {
      stack.push(grandchildren[index]!);
    }
  }
  return output;
}

function isWordElement(node: IndexedBindingNode, localName: string): boolean {
  return (
    node.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    node.visit.localName === localName
  );
}

function wordAttribute(
  node: IndexedBindingNode | undefined,
  localName: string,
): string | undefined {
  return node
    ? exactExpandedAttribute(node.visit, WORDPROCESSINGML_NAMESPACE, localName)
    : undefined;
}
