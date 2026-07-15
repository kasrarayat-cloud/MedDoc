import { canonicalSha256 } from '../template-twin/canonical';
import type {
  FieldResolution,
  TemplateDocIR,
  TemplateField,
} from '../template-twin/ir';
import type { TemplateDocxLimits } from './limits';
import { inspectDocxPackage } from './package-security';
import {
  WORDPROCESSINGML_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  childrenOf,
  exactExpandedAttribute,
  expandedXmlVisits,
  parseOrderedXml,
  tagOf,
  type ExpandedXmlVisit,
  type OrderedXmlNode,
} from './xml';
import {
  failTemplateDocxRender,
  type RenderedFieldProof,
} from './roundtrip-verify';

interface IndexedNode {
  readonly node: OrderedXmlNode;
  readonly path: string;
  readonly visit: ExpandedXmlVisit;
  readonly parent: IndexedNode | null;
}

interface IndexedPart {
  readonly roots: OrderedXmlNode[];
  readonly nodes: readonly IndexedNode[];
  readonly byPath: ReadonlyMap<string, IndexedNode>;
  readonly byNode: ReadonlyMap<OrderedXmlNode, IndexedNode>;
}

export interface ReadbackTemplateDocxOutputInput {
  readonly source: Uint8Array;
  readonly output: Uint8Array;
  readonly ir: TemplateDocIR;
  readonly resolutions: readonly FieldResolution[];
  readonly limits?: Partial<TemplateDocxLimits>;
}

/**
 * Independently reparses completed DOCX bytes. It does not receive renderer
 * patch objects and derives every value hash from the output package itself.
 */
export function readbackTemplateDocxOutput(
  input: ReadbackTemplateDocxOutputInput,
): RenderedFieldProof[] {
  const sourcePackage = inspectDocxPackage(input.source, input.limits);
  const outputPackage = inspectDocxPackage(input.output, input.limits);
  const resolutions = new Map(
    input.resolutions.map((resolution) => [resolution.fieldId, resolution]),
  );
  if (
    resolutions.size !== input.ir.fields.length ||
    input.resolutions.length !== input.ir.fields.length
  ) {
    failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
  }

  const sourceParts = new Map<string, IndexedPart>();
  const outputParts = new Map<string, IndexedPart>();
  const loadPart = (
    partName: string,
    source: boolean,
  ): IndexedPart => {
    const cache = source ? sourceParts : outputParts;
    const existing = cache.get(partName);
    if (existing) return existing;
    const entry = (source ? sourcePackage : outputPackage).zip.entries.get(
      partName,
    );
    if (!entry) failTemplateDocxRender('BINDING_NOT_FOUND');
    const indexed = indexPart(
      parseOrderedXml(entry.bytes, (source ? sourcePackage : outputPackage).limits),
    );
    cache.set(partName, indexed);
    return indexed;
  };

  return input.ir.fields.map((field) => {
    const resolution = resolutions.get(field.fieldId);
    if (!resolution) failTemplateDocxRender('FIELD_RESOLUTION_INVALID');
    const sourcePart = loadPart(field.rendererBinding.partName, true);
    const outputPart = loadPart(field.rendererBinding.partName, false);
    const sourceBound = sourcePart.byPath.get(field.rendererBinding.path);
    const outputBound = outputPart.byPath.get(field.rendererBinding.path);
    if (!sourceBound || !outputBound) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const occurrences = countStableOccurrences(outputPart, field);
    if (occurrences !== 1) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }

    if (field.rowPrototype) {
      // Repeating structures are certification-blocked in safe alpha. A
      // future extractor/renderer must introduce independent row identities.
      if (resolution.value !== null) failTemplateDocxRender('UNSUPPORTED_BINDING');
    }

    if (resolution.value === null || field.detectionStatus === 'unsupported') {
      if (resolution.value !== null) failTemplateDocxRender('FIELD_VALUE_INVALID');
      const mustBePreserved =
        field.detectionStatus === 'unsupported' ||
        field.kind === 'checkbox' ||
        field.rowPrototype;
      if (mustBePreserved) {
        if (
          canonicalSha256(proofContainer(sourceBound)) !==
          canonicalSha256(proofContainer(outputBound))
        ) {
          failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
        }
      } else if (!isBlankBinding(outputPart, outputBound, field)) {
        failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      }
      return {
        fieldId: field.fieldId,
        partName: field.rendererBinding.partName,
        bindingPath: field.rendererBinding.path,
        valueSha256: fieldValueSha256(field.fieldId, null),
        occurrences,
        disposition:
          field.detectionStatus === 'unsupported'
            ? 'preserved_unsupported'
            : mustBePreserved
              ? 'preserved_unresolved'
              : 'unresolved_blank',
      };
    }

    const actual = readFieldValue(outputPart, outputBound, field);
    if (fieldValueSha256(field.fieldId, actual) !== fieldValueSha256(field.fieldId, resolution.value)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return {
      fieldId: field.fieldId,
      partName: field.rendererBinding.partName,
      bindingPath: field.rendererBinding.path,
      valueSha256: fieldValueSha256(field.fieldId, actual),
      occurrences,
      disposition: 'rendered',
    };
  });
}

function isBlankBinding(
  part: IndexedPart,
  bound: IndexedNode,
  field: TemplateField,
): boolean {
  if (field.rendererBinding.bindingType === 'content_control') {
    const properties = directWordChild(bound, 'sdtPr', part);
    const content = directWordChild(bound, 'sdtContent', part);
    if (!properties || !content || wordText(content, part) !== '') return false;
    if (field.kind === 'date') {
      return !wordAttribute(directWordChild(properties, 'date', part), 'fullDate');
    }
    if (field.kind === 'single_select') {
      const combo = directWordChild(properties, 'comboBox', part);
      return !combo || !wordAttribute(descendantsWord(combo, 'lastValue', part)[0], 'val');
    }
    return true;
  }
  if (field.rendererBinding.bindingType === 'legacy_form_field') {
    const formData = descendantsWord(bound, 'ffData', part)[0];
    if (!formData || legacyResultText(bound, part) !== '') return false;
    if (field.kind === 'single_select') {
      const list = descendantsWord(formData, 'ddList', part)[0];
      return !wordAttribute(
        list ? descendantsWord(list, 'result', part)[0] : undefined,
        'val',
      );
    }
    const textInput = descendantsWord(formData, 'textInput', part)[0];
    return !wordAttribute(
      textInput ? descendantsWord(textInput, 'default', part)[0] : undefined,
      'val',
    );
  }
  if (field.rendererBinding.bindingType === 'table_cell') {
    return wordText(bound, part) === '';
  }
  return false;
}

function indexPart(roots: OrderedXmlNode[]): IndexedPart {
  const visits = new Map(
    expandedXmlVisits(roots).map((visit) => [visit.node, visit]),
  );
  const nodes: IndexedNode[] = [];
  const byPath = new Map<string, IndexedNode>();
  const byNode = new Map<OrderedXmlNode, IndexedNode>();
  const walk = (
    children: OrderedXmlNode[],
    parentPath: string,
    parent: IndexedNode | null,
  ): void => {
    const counts = new Map<string, number>();
    for (const node of children) {
      const tag = tagOf(node);
      if (!tag || tag === '#text' || tag === '?xml') continue;
      const ordinal = counts.get(tag) ?? 0;
      counts.set(tag, ordinal + 1);
      const path = `${parentPath}/${tag}[${ordinal}]`;
      const visit = visits.get(node);
      if (!visit || byPath.has(path)) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
      const indexed: IndexedNode = { node, path, visit, parent };
      nodes.push(indexed);
      byPath.set(path, indexed);
      byNode.set(node, indexed);
      walk(childrenOf(node), path, indexed);
    }
  };
  walk(roots, '', null);
  return { roots, nodes, byPath, byNode };
}

function proofContainer(node: IndexedNode): OrderedXmlNode {
  if (node.visit.localName !== 'fldChar') return node.node;
  let parent: IndexedNode | null = node;
  while (parent && !isWordElement(parent, 'p')) parent = parent.parent;
  return parent?.node ?? node.node;
}

function countStableOccurrences(part: IndexedPart, field: TemplateField): number {
  const binding = field.rendererBinding;
  if (binding.bindingType === 'content_control') {
    return part.nodes.filter((node) => {
      if (!isWordElement(node, 'sdt')) return false;
      const properties = directWordChild(node, 'sdtPr', part);
      if (!properties) return false;
      if (binding.sdtId) {
        return wordAttribute(directWordChild(properties, 'id', part), 'val') === binding.sdtId;
      }
      if (binding.tag) {
        return wordAttribute(directWordChild(properties, 'tag', part), 'val') === binding.tag;
      }
      if (binding.alias) {
        return wordAttribute(directWordChild(properties, 'alias', part), 'val') === binding.alias;
      }
      return node.path === binding.path;
    }).length;
  }
  if (binding.bindingType === 'legacy_form_field' && binding.legacyName) {
    return part.nodes.filter((node) => {
      if (!isWordElement(node, 'fldChar')) return false;
      const formData = descendantsWord(node, 'ffData', part)[0];
      const name = formData ? descendantsWord(formData, 'name', part)[0] : undefined;
      return wordAttribute(name, 'val') === binding.legacyName;
    }).length;
  }
  return part.byPath.has(binding.path) ? 1 : 0;
}

function readFieldValue(
  part: IndexedPart,
  bound: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  switch (field.rendererBinding.bindingType) {
    case 'content_control':
      return readContentControl(part, bound, field);
    case 'legacy_form_field':
      return readLegacyField(part, bound, field);
    case 'table_cell':
      return convertDisplayedValue(field, wordText(bound, part));
    case 'repeating_row':
      failTemplateDocxRender('UNSUPPORTED_BINDING');
  }
}

function readContentControl(
  part: IndexedPart,
  control: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  if (!isWordElement(control, 'sdt')) failTemplateDocxRender('BINDING_NOT_FOUND');
  const properties = directWordChild(control, 'sdtPr', part);
  const content = directWordChild(control, 'sdtContent', part);
  if (!properties || !content) failTemplateDocxRender('BINDING_NOT_FOUND');
  if (
    descendantsWord(properties, 'showingPlcHdr', part).length > 0 ||
    descendantsWord(content, 'rStyle', part).some(
      (style) => wordAttribute(style, 'val') === 'PlaceholderText',
    )
  ) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }

  if (field.kind === 'checkbox') {
    const checkbox = descendantsByLocal(properties, 'checkbox', part).find(
      (node) => node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
    );
    const checked = checkbox
      ? descendantsByLocal(checkbox, 'checked', part).find(
          (node) => node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
        )
      : undefined;
    const raw = namespacedAttribute(
      checked,
      WORDPROCESSINGML_2010_NAMESPACE,
      'val',
    );
    if (raw !== '0' && raw !== '1' && raw !== 'true' && raw !== 'false') {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const value = raw === '1' || raw === 'true';
    const state = checkbox
      ? descendantsByLocal(
          checkbox,
          value ? 'checkedState' : 'uncheckedState',
          part,
        ).find(
          (node) =>
            node.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE,
        )
      : undefined;
    const glyphCode = namespacedAttribute(
      state,
      WORDPROCESSINGML_2010_NAMESPACE,
      'val',
    );
    const glyph = glyphCode && /^[a-f0-9]{1,6}$/i.test(glyphCode)
      ? String.fromCodePoint(Number.parseInt(glyphCode, 16))
      : value
        ? '☒'
        : '☐';
    if (wordText(content, part) !== glyph) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }

  if (field.kind === 'date') {
    const date = directWordChild(properties, 'date', part);
    const fullDate = wordAttribute(date, 'fullDate');
    const match = /^(\d{4}-\d{2}-\d{2})T/.exec(fullDate ?? '');
    if (!date || !match) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    const value = match[1]!;
    const format = wordAttribute(descendantsWord(date, 'dateFormat', part)[0], 'val');
    if (wordText(content, part) !== formatDate(value, format)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }

  const value = convertDisplayedValue(field, wordText(content, part));
  if (field.kind === 'single_select') {
    const combo = directWordChild(properties, 'comboBox', part);
    const lastValue = combo
      ? wordAttribute(descendantsWord(combo, 'lastValue', part)[0], 'val')
      : undefined;
    if (lastValue !== undefined && lastValue !== value) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
  }
  return value;
}

function readLegacyField(
  part: IndexedPart,
  begin: IndexedNode,
  field: TemplateField,
): FieldResolution['value'] {
  const formData = descendantsWord(begin, 'ffData', part)[0];
  if (!formData) failTemplateDocxRender('BINDING_NOT_FOUND');
  const resultText = legacyResultText(begin, part);
  if (field.kind === 'checkbox') {
    const checkbox = descendantsWord(formData, 'checkBox', part)[0];
    const raw = wordAttribute(
      checkbox ? descendantsWord(checkbox, 'checked', part)[0] : undefined,
      'val',
    );
    if (raw !== '0' && raw !== '1' && raw !== 'true' && raw !== 'false') {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const value = raw === '1' || raw === 'true';
    if (resultText && resultText !== (value ? '☒' : '☐')) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return value;
  }
  if (field.kind === 'single_select') {
    const list = descendantsWord(formData, 'ddList', part)[0];
    const raw = wordAttribute(
      list ? descendantsWord(list, 'result', part)[0] : undefined,
      'val',
    );
    if (!raw || !/^(?:0|[1-9][0-9]*)$/.test(raw)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    const option = field.allowedOptions.find((candidate) => candidate.ordinal === Number(raw));
    if (!option || (resultText && resultText !== option.displayText)) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return option.value;
  }
  const textInput = descendantsWord(formData, 'textInput', part)[0];
  const defaultValue = wordAttribute(
    textInput ? descendantsWord(textInput, 'default', part)[0] : undefined,
    'val',
  );
  if (defaultValue !== undefined && defaultValue !== null && resultText && defaultValue !== resultText) {
    failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
  }
  return convertDisplayedValue(field, defaultValue ?? resultText);
}

function convertDisplayedValue(
  field: TemplateField,
  displayed: string,
): FieldResolution['value'] {
  if (field.kind === 'single_select') {
    const options = field.allowedOptions.filter(
      (option) => option.displayText === displayed,
    );
    if (options.length !== 1) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    return options[0]!.value;
  }
  if (field.kind === 'multi_select') {
    const displayedOptions = displayed.split(';').map((value) => value.trim());
    const values = displayedOptions.map((display) => {
      const options = field.allowedOptions.filter(
        (option) => option.displayText === display,
      );
      if (options.length !== 1) failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
      return options[0]!.value;
    });
    if (new Set(values).size !== values.length) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return values;
  }
  if (field.kind === 'number') {
    const number = Number(displayed);
    if (!Number.isFinite(number) || String(number) !== displayed) {
      failTemplateDocxRender('ROUNDTRIP_FIELD_MISMATCH');
    }
    return number;
  }
  return displayed;
}

function legacyResultText(begin: IndexedNode, part: IndexedPart): string {
  let paragraph: IndexedNode | null = begin;
  while (paragraph && !isWordElement(paragraph, 'p')) paragraph = paragraph.parent;
  if (!paragraph) return '';
  const nodes = descendantsByLocal(paragraph, '', part);
  const startIndex = nodes.findIndex((node) => node === begin);
  let depth = 0;
  let inResult = false;
  const text: string[] = [];
  for (const node of nodes.slice(startIndex)) {
    if (isWordElement(node, 'fldChar')) {
      const type = wordAttribute(node, 'fldCharType');
      if (type === 'begin') depth += 1;
      else if (type === 'separate' && depth === 1) inResult = true;
      else if (type === 'end') {
        depth -= 1;
        if (depth === 0) break;
      }
      continue;
    }
    if (inResult && depth === 1 && isWordElement(node, 't')) {
      text.push(nodeText(node.node));
    }
  }
  return text.join('');
}

function directWordChild(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode | undefined {
  return childrenOf(node.node)
    .map((child) => part.byNode.get(child))
    .find((child): child is IndexedNode => Boolean(child && isWordElement(child, wanted)));
}

function descendantsWord(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode[] {
  return descendantsByLocal(node, wanted, part).filter(
    (candidate) => candidate.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE,
  );
}

function descendantsByLocal(
  node: IndexedNode,
  wanted: string,
  part: IndexedPart,
): IndexedNode[] {
  const output: IndexedNode[] = [];
  const stack = [...childrenOf(node.node)].reverse();
  while (stack.length > 0) {
    const child = stack.pop()!;
    if (tagOf(child) === '#text' || tagOf(child) === '?xml') continue;
    const indexed = part.byNode.get(child);
    if (!indexed) failTemplateDocxRender('ROUNDTRIP_PACKAGE_INVALID');
    if (!wanted || indexed.visit.localName === wanted) output.push(indexed);
    const grandchildren = childrenOf(child);
    for (let index = grandchildren.length - 1; index >= 0; index -= 1) {
      stack.push(grandchildren[index]!);
    }
  }
  return output;
}

function isWordElement(node: IndexedNode, wanted: string): boolean {
  return (
    node.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    node.visit.localName === wanted
  );
}

function wordAttribute(
  node: IndexedNode | undefined,
  local: string,
): string | undefined {
  if (!node) return undefined;
  return exactExpandedAttribute(node.visit, WORDPROCESSINGML_NAMESPACE, local);
}

function namespacedAttribute(
  node: IndexedNode | undefined,
  namespaceUri: string,
  local: string,
): string | undefined {
  if (!node) return undefined;
  return exactExpandedAttribute(node.visit, namespaceUri, local);
}

function wordText(node: IndexedNode, part: IndexedPart): string {
  const output: string[] = [];
  const nodes = [node, ...descendantsByLocal(node, '', part)];
  for (const candidate of nodes) {
    if (candidate.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE) continue;
    if (candidate.visit.localName === 't') output.push(nodeText(candidate.node));
    else if (candidate.visit.localName === 'tab') output.push('\t');
    else if (candidate.visit.localName === 'br' || candidate.visit.localName === 'cr') {
      output.push('\n');
    }
  }
  return output.join('');
}

function nodeText(node: OrderedXmlNode): string {
  const value = node[tagOf(node)];
  if (!Array.isArray(value)) return typeof value === 'string' ? value : '';
  return value
    .map((child) =>
      tagOf(child as OrderedXmlNode) === '#text'
        ? String((child as OrderedXmlNode)['#text'] ?? '')
        : '',
    )
    .join('')
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) =>
      String.fromCodePoint(Number.parseInt(hex, 16)),
    )
    .replace(/&#([0-9]+);/g, (_, value: string) =>
      String.fromCodePoint(Number.parseInt(value, 10)),
    )
    .replaceAll('&quot;', '"')
    .replaceAll('&apos;', "'")
    .replaceAll('&gt;', '>')
    .replaceAll('&lt;', '<')
    .replaceAll('&amp;', '&');
}

function formatDate(value: string, format: string | undefined): string {
  if (!format) return value;
  const [year, month, day] = value.split('-');
  if (!year || !month || !day || /[A-Za-z]/.test(format.replace(/yyyy|yy|MM|M|dd|d/g, ''))) {
    return value;
  }
  return format.replace(/yyyy|yy|MM|M|dd|d/g, (token) => {
    if (token === 'yyyy') return year;
    if (token === 'yy') return year.slice(-2);
    if (token === 'MM') return month;
    if (token === 'M') return String(Number(month));
    if (token === 'dd') return day;
    return String(Number(day));
  });
}

function fieldValueSha256(
  fieldId: string,
  value: FieldResolution['value'],
): string {
  return canonicalSha256({ fieldId, value });
}
