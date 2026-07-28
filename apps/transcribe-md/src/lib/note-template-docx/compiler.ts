import { createHash } from 'node:crypto';

import { canonicalSha256 } from '../template-twin/canonical';
import {
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_IR_SCHEMA_VERSION,
  TemplateDocIRSchema,
  type RendererBinding,
  type OrdinaryPlaceholderTokenBinding,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTable,
  type UnsupportedElement,
} from '../template-twin/ir';
import { failTemplateDocx } from './errors';
import type { TemplateDocxLimits } from './limits';
import {
  inspectDocxPackage,
  type InspectedDocxPackage,
} from './package-security';
import {
  WORDPROCESSINGML_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  childrenOf,
  descendants,
  directChild,
  directChildren,
  exactExpandedAttribute,
  getAttribute,
  localName,
  parseOrderedXml,
  tagOf,
  visibleText,
  type OrderedXmlNode,
} from './xml';
import {
  certifiedBindingFingerprintSha256,
  certifyOrdinaryPlaceholderTokenBinding,
  deriveOoxmlBindingIdentity,
  hasStrongNativeIdentity,
  indexBindingXmlPart,
  nativeIdentityFromRendererBinding,
  sameNativeIdentity,
  type IndexedBindingPart,
  type IndexedBindingNode,
} from './binding-fingerprint';

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' as const;
const MAX_TABLE_ROWS = 100;
const ORDINARY_PLACEHOLDER_RE =
  /(?:<<[^<>\r\n]{1,160}>>|\[\[[^\[\]\r\n]{1,160}\]\]|\{\{[^{}\r\n]{1,160}\}\}|_{3,160})/i;
const ORDINARY_PLACEHOLDER_GLOBAL_RE =
  /<<[^<>\r\n]{1,160}>>|\[\[[^\[\]\r\n]{1,160}\]\]|\{\{[^{}\r\n]{1,160}\}\}|_{3,160}/giu;
const PLACEHOLDER_DELIMITER_FRAGMENT_RE = /<<|>>|\[\[|\]\]|\{\{|\}\}|_{3,}/u;
const REQUIRED_LABELED_BLANK_RE =
  /\b(?:required|must complete|enter|document)\b[^:\n]{0,100}:\s*$/i;

/**
 * Exact compiler-only admission profile for the Word-authored blank cells in
 * the WM IOV compatibility slice. The paragraph tab is a static tab-stop
 * definition under w:pPr; it is not mutable content and must remain intact.
 *
 * The immutable table-cell identity already fingerprints the complete cell
 * and paragraph properties, so renderer/readback can distinguish this shape
 * from a plain blank cell without trusting a mutable profile label.
 */
export const TAB_ONLY_BLANK_TABLE_CELL_PROFILE =
  'TAB_ONLY_BLANK_TABLE_CELL_V1' as const;
export const ORDINARY_PLACEHOLDER_TOKEN_PROFILE =
  'ORDINARY_PLACEHOLDER_TOKEN_V1' as const;

type TemplateDocNode = TemplateDocIR['nodes'][number];
type TemplateDocPart = TemplateDocIR['parts'][number];
type TemplateTableCell = TemplateTable['cells'][number];

export interface CompileTemplateDocxOptions {
  limits?: Partial<TemplateDocxLimits>;
}

interface MutableTableContext {
  tableId: string;
  tableIndex: number;
  rowIndex: number;
  cellIndex: number;
  cellFieldIds: string[];
  repeatAncestorPath: string | null;
}

interface WalkContext {
  partName: string;
  table: MutableTableContext | null;
  repeatAncestorPath: string | null;
  containerText: string | null;
  insideFieldContent: boolean;
}

interface CompilerState {
  sourceSha256: string;
  limits: TemplateDocxLimits;
  fields: TemplateField[];
  tables: TemplateTable[];
  nodes: TemplateDocNode[];
  unsupported: UnsupportedElement[];
  unsupportedKeys: Set<string>;
  nextDisplayOrder: number;
  nextBindingOrdinal: number;
  tableCountByPart: Map<string, number>;
  comboBoxes: number;
  bindingIndexes: Map<string, IndexedBindingPart>;
}

interface TableRowLocation {
  node: OrderedXmlNode;
  path: string;
  repeatAncestorPath: string | null;
}

export function compileTemplateDocx(
  source: Uint8Array,
  options: CompileTemplateDocxOptions = {},
): TemplateDocIR {
  const inspected = inspectDocxPackage(source, options.limits);
  const state: CompilerState = {
    sourceSha256: inspected.sourceSha256,
    limits: inspected.limits,
    fields: [],
    tables: [],
    nodes: [],
    unsupported: [],
    unsupportedKeys: new Set(),
    nextDisplayOrder: 0,
    nextBindingOrdinal: 0,
    tableCountByPart: new Map(),
    comboBoxes: 0,
    bindingIndexes: new Map(),
  };

  const parsedParts = new Map<string, OrderedXmlNode[]>();
  const structuralParts = [
    inspected.mainPartName,
    ...inspected.headerPartNames,
    ...inspected.footerPartNames,
  ];

  for (const partName of structuralParts) {
    const entry = inspected.zip.entries.get(partName);
    if (!entry) failTemplateDocx('OPC_REQUIRED_PART_MISSING');
    const tree = parseOrderedXml(entry.bytes, inspected.limits);
    parsedParts.set(partName, tree);
    state.bindingIndexes.set(partName, indexBindingXmlPart(tree));
    walkNodes(tree, '', defaultContext(partName), state);
  }
  // Identity admission is package-wide even though safe-alpha field extraction
  // is limited to the main/header/footer stories. Word may renumber a colliding
  // SDT found in an auxiliary story when it opens the package.
  for (const [partName, entry] of inspected.zip.entries) {
    if (
      state.bindingIndexes.has(partName) ||
      !/^word\/.*\.xml$/i.test(partName)
    ) {
      continue;
    }
    state.bindingIndexes.set(
      partName,
      indexBindingXmlPart(parseOrderedXml(entry.bytes, inspected.limits)),
    );
  }
  blockDuplicateNativeBindingIdentities(
    state,
    new Set(structuralParts),
    inspected.mainPartName,
  );
  blockAmbiguousAnonymousBindingIdentities(state);

  const parts = buildPartManifest(inspected, parsedParts);
  const staticContentSha256 = canonicalSha256(
    parts.map((part) => ({
      partName: part.partName,
      staticSha256: part.staticSha256,
    })),
  );
  const structureSha256 = canonicalSha256({
    fields: state.fields,
    tables: state.tables,
    nodes: state.nodes,
    unsupported: state.unsupported,
  });

  const candidate: TemplateDocIR = {
    irSchemaVersion: TEMPLATE_TWIN_IR_SCHEMA_VERSION,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    source: {
      sha256: inspected.sourceSha256,
      sizeBytes: inspected.zip.source.length,
      mimeType: DOCX_MIME,
    },
    parts,
    nodes: state.nodes,
    fields: state.fields,
    tables: state.tables,
    unsupported: state.unsupported,
    structureSha256,
    staticContentSha256,
    stats: {
      totalFields: state.fields.length,
      dropdowns:
        state.fields.filter((field) => field.kind === 'single_select').length -
        state.comboBoxes,
      comboBoxes: state.comboBoxes,
      checkboxes: state.fields.filter((field) => field.kind === 'checkbox')
        .length,
      dateControls: state.fields.filter((field) => field.kind === 'date')
        .length,
      tables: state.tables.length,
      repeatingTables: state.tables.filter(
        (table) => table.kind === 'repeating_table',
      ).length,
      headers: inspected.headerPartNames.length,
      footers: inspected.footerPartNames.length,
      unsupported: state.unsupported.length,
      blockingUnsupported: state.unsupported.filter(
        (item) => item.blocksCertification,
      ).length,
    },
  };

  const result = TemplateDocIRSchema.safeParse(candidate);
  if (!result.success) failTemplateDocx('IR_VALIDATION_FAILED');
  return result.data;
}

interface NativeBindingOccurrence {
  readonly partName: string;
  readonly path: string;
  readonly label: string | null;
}

/**
 * Fail-closed native identity admission.
 *
 * SDT IDs are package-wide Word identities: an omitted, malformed, repeated,
 * or colliding ID can be reassigned when Word opens any story in the document.
 * Tags, aliases, and visible labels are intentionally not substitutes for an
 * SDT ID. Legacy field-name scope is not proven outside the main story in the
 * safe alpha, so those controls are blocked there and names are conservatively
 * required to be unique package-wide.
 */
function blockDuplicateNativeBindingIdentities(
  state: CompilerState,
  structuralParts: ReadonlySet<string>,
  mainPartName: string,
): void {
  const sdtIds = new Map<string, NativeBindingOccurrence[]>();
  const legacyNames = new Map<string, NativeBindingOccurrence[]>();
  const blockedLocations = new Set<string>();

  for (const [partName, index] of state.bindingIndexes) {
    for (const indexed of index.nodes) {
      if (isIndexedWordElement(indexed, 'sdt')) {
        const identity = deriveOoxmlBindingIdentity(
          index,
          indexed,
          'content_control',
        );
        const occurrence = {
          partName,
          path: indexed.path,
          label:
            identity?.nativeIdentity.alias ??
            identity?.nativeIdentity.tag ??
            null,
        };
        const properties = directIndexedWordChildren(index, indexed, 'sdtPr');
        const idNodes =
          properties.length === 1
            ? directIndexedWordChildren(index, properties[0]!, 'id')
            : [];
        if (idNodes.length === 0) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'MISSING_SDT_ID',
            'This Word control has no stable internal control ID. Word can assign a different ID when the file opens, so recreate the control in Word and upload a new template version.',
            blockedLocations,
          );
        } else if (idNodes.length !== 1) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'MULTIPLE_SDT_ID',
            'This Word control contains more than one internal control ID. The certified field identity would be ambiguous, so recreate the control in Word and upload a new template version.',
            blockedLocations,
          );
        } else {
          const rawId = exactExpandedAttribute(
            idNodes[0]!.visit,
            WORDPROCESSINGML_NAMESPACE,
            'val',
          );
          const canonicalId = canonicalDecimalIdentity(rawId);
          if (!canonicalId) {
            addNativeIdentityBlocker(
              state,
              occurrence,
              'INVALID_SDT_ID',
              'This Word control has an invalid internal control ID. Its identity cannot be preserved safely, so recreate the control in Word and upload a new template version.',
              blockedLocations,
            );
          } else {
            pushIdentityOccurrence(sdtIds, canonicalId, occurrence);
          }
        }
        if (!structuralParts.has(partName)) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'UNSUPPORTED_AUXILIARY_STORY_CONTENT_CONTROL',
            'A Word control was found in notes, comments, or another auxiliary document story that Template Twin safe alpha cannot map and verify. Move it to the document body, header, or footer, or remove it before upload.',
            blockedLocations,
          );
        }
        continue;
      }

      const contentControl = deriveOoxmlBindingIdentity(
        index,
        indexed,
        'content_control',
      );
      if (contentControl) continue;

      const legacyField = deriveOoxmlBindingIdentity(
        index,
        indexed,
        'legacy_form_field',
      );
      if (legacyField) {
        const occurrence = {
          partName,
          path: indexed.path,
          label: legacyField.nativeIdentity.legacyName,
        };
        const formData = indexedWordDescendants(index, indexed, 'ffData')[0];
        const names = formData
          ? indexedWordDescendants(index, formData, 'name')
          : [];
        const legacyName =
          names.length === 1
            ? exactExpandedAttribute(
                names[0]!.visit,
                WORDPROCESSINGML_NAMESPACE,
                'val',
              )?.trim()
            : undefined;
        if (names.length === 0 || !legacyName) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'MISSING_LEGACY_FORM_FIELD_NAME',
            'This legacy Word field has no stable internal name. Rename or recreate it in the original document before certification.',
            blockedLocations,
          );
        } else if (names.length !== 1) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'MULTIPLE_LEGACY_FORM_FIELD_NAME',
            'This legacy Word field contains more than one internal name. Recreate it with one unique name before certification.',
            blockedLocations,
          );
        } else {
          pushIdentityOccurrence(legacyNames, canonicalLegacyName(legacyName), {
            ...occurrence,
            label: legacyName,
          });
        }
        if (partName !== mainPartName) {
          addNativeIdentityBlocker(
            state,
            occurrence,
            'UNSUPPORTED_LEGACY_FORM_FIELD_STORY',
            'Legacy Word form fields outside the main document body are not supported in Template Twin safe alpha because their Office identity behavior has not been proven. Move the field to the body or use a modern Word control.',
            blockedLocations,
          );
        }
      } else if (isIndexedWordElement(indexed, 'fldChar')) {
        // Non-form Word field markers are handled by the active-field policy,
        // not by the legacy form identity census.
        continue;
      }
    }
  }

  addDuplicateIdentityBlockers(
    state,
    sdtIds,
    'DUPLICATE_SDT_ID',
    'Two Word controls share the same internal control ID. Word can silently renumber one when the file opens, so this template version cannot be certified. Recreate the duplicate control with a unique ID and upload a new version.',
    blockedLocations,
  );
  addDuplicateIdentityBlockers(
    state,
    legacyNames,
    'DUPLICATE_LEGACY_FORM_FIELD_NAME',
    'Two legacy Word form fields share one internal name. Their identities would be ambiguous, so rename them uniquely in the original template and upload a new version before certification.',
    blockedLocations,
  );

  if (blockedLocations.size > 0) {
    state.fields = state.fields.map((field) =>
      blockedLocations.has(bindingLocationKey(field.rendererBinding))
        ? { ...field, detectionStatus: 'unsupported' }
        : field,
    );
  }
}

function addNativeIdentityBlocker(
  state: CompilerState,
  occurrence: NativeBindingOccurrence,
  code: string,
  detail: string,
  blockedLocations: Set<string>,
): void {
  blockedLocations.add(
    nativeBindingLocationKey(occurrence.partName, occurrence.path),
  );
  addUnsupported(state, {
    code,
    partName: occurrence.partName,
    path: occurrence.path,
    label: occurrence.label,
    detail,
    clinicallyMaterial: true,
    blocksCertification: true,
  });
}

function isIndexedWordElement(
  node: IndexedBindingNode,
  localName: string,
): boolean {
  return (
    node.visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
    node.visit.localName === localName
  );
}

function directIndexedWordChildren(
  part: IndexedBindingPart,
  parent: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  return childrenOf(parent.node)
    .map((child) => part.byNode.get(child))
    .filter((child): child is IndexedBindingNode =>
      Boolean(child && isIndexedWordElement(child, localName)),
    );
}

function indexedWordDescendants(
  part: IndexedBindingPart,
  parent: IndexedBindingNode,
  localName: string,
): IndexedBindingNode[] {
  const output: IndexedBindingNode[] = [];
  const stack = [...childrenOf(parent.node)].reverse();
  while (stack.length > 0) {
    const childNode = stack.pop()!;
    const child = part.byNode.get(childNode);
    if (!child) continue;
    if (isIndexedWordElement(child, localName)) output.push(child);
    stack.push(...childrenOf(child.node).reverse());
  }
  return output;
}

function pushIdentityOccurrence(
  groups: Map<string, NativeBindingOccurrence[]>,
  key: string,
  occurrence: NativeBindingOccurrence,
): void {
  const group = groups.get(key) ?? [];
  group.push(occurrence);
  groups.set(key, group);
}

function addDuplicateIdentityBlockers(
  state: CompilerState,
  groups: ReadonlyMap<string, readonly NativeBindingOccurrence[]>,
  code: string,
  detail: string,
  blockedLocations: Set<string>,
): void {
  for (const occurrences of groups.values()) {
    if (occurrences.length < 2) continue;
    for (const occurrence of occurrences) {
      blockedLocations.add(
        nativeBindingLocationKey(occurrence.partName, occurrence.path),
      );
      addUnsupported(state, {
        code,
        partName: occurrence.partName,
        path: occurrence.path,
        label: occurrence.label,
        detail,
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
  }
}

function bindingLocationKey(binding: RendererBinding): string {
  return nativeBindingLocationKey(binding.partName, binding.path);
}

function nativeBindingLocationKey(partName: string, path: string): string {
  return `${partName}\0${path}`;
}

function canonicalDecimalIdentity(value: string | undefined): string | null {
  if (!value || !/^[+-]?[0-9]+$/.test(value)) return null;
  try {
    const parsed = BigInt(value);
    // Word's object model exposes ContentControl.ID as an unsigned 32-bit
    // number even though WordprocessingML commonly persists the same bits as
    // a signed decimal. Treat -1 and 4294967295 (and the rest of that overlap)
    // as one native ID without wrapping arbitrary out-of-range input.
    if (parsed >= BigInt('-2147483648') && parsed <= BigInt('4294967295')) {
      return `word-uint32:${BigInt.asUintN(32, parsed).toString(10)}`;
    }
    return null;
  } catch {
    return null;
  }
}

function canonicalLegacyName(value: string): string {
  return value.normalize('NFC').toLocaleLowerCase('en-US');
}

function blockAmbiguousAnonymousBindingIdentities(state: CompilerState): void {
  const groups = new Map<string, TemplateField[]>();
  for (const field of state.fields) {
    const binding = field.rendererBinding;
    if (
      binding.bindingType === 'table_cell' ||
      binding.bindingType === 'repeating_row' ||
      hasStrongNativeIdentity({
        sdtId: binding.sdtId,
        tag: binding.tag,
        alias: binding.alias,
        legacyName: binding.legacyName,
      })
    ) {
      continue;
    }
    const key = `${binding.bindingType}:${binding.sourceBindingIdentitySha256}`;
    const group = groups.get(key) ?? [];
    group.push(field);
    groups.set(key, group);
  }
  const blockedFieldIds = new Set<string>();
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    for (const field of group) {
      blockedFieldIds.add(field.fieldId);
      addUnsupported(state, {
        code: 'AMBIGUOUS_ANONYMOUS_BINDING_IDENTITY',
        partName: field.rendererBinding.partName,
        path: field.rendererBinding.path,
        label: field.originalLabel,
        detail:
          'This field has no native Word identity and is indistinguishable from another control. Add a unique Word tag, alias, ID, or legacy name before certification.',
        clinicallyMaterial: field.clinicallyMaterial,
        blocksCertification: true,
      });
    }
  }
  if (blockedFieldIds.size > 0) {
    state.fields = state.fields.map((field) =>
      blockedFieldIds.has(field.fieldId)
        ? { ...field, detectionStatus: 'unsupported' }
        : field,
    );
  }
}

function defaultContext(partName: string): WalkContext {
  return {
    partName,
    table: null,
    repeatAncestorPath: null,
    containerText: null,
    insideFieldContent: false,
  };
}

function createCertifiedRendererBinding(input: {
  fieldId: string;
  node: OrderedXmlNode;
  context: WalkContext;
  bindingType:
    | 'content_control'
    | 'legacy_form_field'
    | 'table_cell'
    | 'ordinary_placeholder';
  bindingProfile?: RendererBinding['bindingProfile'];
  ordinaryPlaceholder?: OrdinaryPlaceholderTokenBinding;
  sdtId: string | null;
  tag: string | null;
  alias: string | null;
  legacyName: string | null;
  sourceControlSha256: string;
  originalContentSha256: string;
  state: CompilerState;
}): RendererBinding {
  const index = input.state.bindingIndexes.get(input.context.partName);
  const indexed = index?.byNode.get(input.node);
  if (!index || !indexed) failTemplateDocx('IR_VALIDATION_FAILED');
  const sourceIdentity = deriveOoxmlBindingIdentity(
    index,
    indexed,
    input.bindingType,
    input.ordinaryPlaceholder,
  );
  if (!sourceIdentity) failTemplateDocx('IR_VALIDATION_FAILED');
  const repeatAncestor = input.context.repeatAncestorPath
    ? index.byPath.get(input.context.repeatAncestorPath)
    : null;
  if (input.context.repeatAncestorPath && !repeatAncestor) {
    failTemplateDocx('IR_VALIDATION_FAILED');
  }
  const base: Omit<RendererBinding, 'certifiedBindingSha256'> = {
    partName: input.context.partName,
    bindingType: input.bindingType,
    ...(input.bindingProfile === undefined
      ? {}
      : { bindingProfile: input.bindingProfile }),
    ...(input.ordinaryPlaceholder === undefined
      ? {}
      : { ordinaryPlaceholder: input.ordinaryPlaceholder }),
    path: indexed.path,
    canonicalPath: indexed.canonicalPath,
    ordinal: input.state.nextBindingOrdinal++,
    sdtId: input.sdtId,
    tag: input.tag,
    alias: input.alias,
    legacyName: input.legacyName,
    tableIndex: input.context.table?.tableIndex ?? null,
    rowIndex: input.context.table?.rowIndex ?? null,
    cellIndex: input.context.table?.cellIndex ?? null,
    repeatAncestorPath: input.context.repeatAncestorPath,
    canonicalRepeatAncestorPath: repeatAncestor?.canonicalPath ?? null,
    sourceControlSha256: input.sourceControlSha256,
    sourceBindingIdentitySha256: sourceIdentity.identitySha256,
    originalContentSha256: input.originalContentSha256,
  };
  const certifiedNativeIdentity = nativeIdentityFromRendererBinding(base);
  if (
    !sameNativeIdentity(certifiedNativeIdentity, sourceIdentity.nativeIdentity)
  ) {
    failTemplateDocx('IR_VALIDATION_FAILED');
  }
  return {
    ...base,
    certifiedBindingSha256: certifiedBindingFingerprintSha256({
      fieldId: input.fieldId,
      partName: base.partName,
      canonicalPath: base.canonicalPath,
      bindingType: base.bindingType,
      bindingProfile: base.bindingProfile,
      ordinaryPlaceholder: base.ordinaryPlaceholder,
      bindingOrdinal: base.ordinal,
      nativeIdentity: certifiedNativeIdentity,
      sourceControlSha256: base.sourceControlSha256,
      sourceBindingIdentitySha256: base.sourceBindingIdentitySha256,
      tableLocation: {
        tableIndex: base.tableIndex,
        rowIndex: base.rowIndex,
        cellIndex: base.cellIndex,
      },
      canonicalRepeatAncestorPath: base.canonicalRepeatAncestorPath,
    }),
  };
}

function walkNodes(
  nodes: OrderedXmlNode[],
  parentPath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const siblingCounts = new Map<string, number>();

  for (const node of nodes) {
    const tag = tagOf(node);
    if (!tag || tag === '?xml' || tag === '#text') continue;
    const siblingIndex = siblingCounts.get(tag) ?? 0;
    siblingCounts.set(tag, siblingIndex + 1);
    const nodePath = structuralPath(parentPath, tag, siblingIndex, state);
    const local = localName(tag);

    if (local === 'AlternateContent') {
      addUnsupported(state, {
        code: 'ALTERNATE_CONTENT_UNSUPPORTED_SAFE_ALPHA',
        partName: context.partName,
        path: nodePath,
        label: null,
        detail:
          'This Word compatibility block has multiple representations. Template Twin safe alpha cannot prove one stable fill location.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
      addNode(state, {
        partName: context.partName,
        path: nodePath,
        kind: 'unsupported',
        fieldId: null,
        tableId: context.table?.tableId ?? null,
        staticTextSha256: canonicalSha256(node),
        bookmarkNames: bookmarkNames(node),
      });
      continue;
    }

    if (local === 'tbl') {
      processTable(node, nodePath, context, state);
      continue;
    }
    if (local === 'sdt') {
      processContentControl(node, nodePath, context, state);
      continue;
    }
    if (local === 'p') {
      processParagraph(node, nodePath, context, state);
      continue;
    }
    if (local === 'fldChar' && getAttribute(node, 'fldCharType') === 'begin') {
      processLegacyField(node, nodePath, context, state);
      continue;
    }
    if (local === 'fldSimple') {
      inspectDynamicField(
        getAttribute(node, 'instr') ?? '',
        node,
        nodePath,
        context,
        state,
      );
    } else if (local === 'instrText') {
      inspectDynamicField(visibleText(node), node, nodePath, context, state);
    } else if (local === 'altChunk') {
      addUnsupported(state, {
        code: 'ALT_CHUNK_UNSUPPORTED',
        partName: context.partName,
        path: nodePath,
        label: null,
        detail:
          'Imported alternative-format content is not supported in Template Twin v1.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }

    walkNodes(childrenOf(node), nodePath, context, state);
  }
}

function processParagraph(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const text = normalizeLabel(visibleText(node));
  const hasFillableDescendant =
    descendants(node, 'sdt').length > 0 ||
    descendants(node, 'fldChar').some(
      (field) => getAttribute(field, 'fldCharType') === 'begin',
    );

  const ordinaryPlaceholder =
    !hasFillableDescendant &&
    !context.insideFieldContent &&
    context.repeatAncestorPath === null
      ? detectOrdinaryPlaceholderToken(node, context.partName, state)
      : null;
  if (
    text &&
    !context.insideFieldContent &&
    descendants(node, 'fldChar').length > 0 &&
    PLACEHOLDER_DELIMITER_FRAGMENT_RE.test(text)
  ) {
    addUnsupported(state, {
      code: 'UNBOUND_ORDINARY_PLACEHOLDER',
      partName: context.partName,
      path: nodePath,
      label: text,
      detail:
        'A visible placeholder overlaps a Word field boundary and cannot be bound independently.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }
  if (ordinaryPlaceholder) {
    createOrdinaryPlaceholderField(
      node,
      nodePath,
      context,
      ordinaryPlaceholder,
      state,
    );
    walkNodes(
      childrenOf(node),
      nodePath,
      { ...context, containerText: text || null },
      state,
    );
    return;
  }

  if (
    text &&
    !hasFillableDescendant &&
    !context.insideFieldContent &&
    (ORDINARY_PLACEHOLDER_RE.test(text) ||
      PLACEHOLDER_DELIMITER_FRAGMENT_RE.test(text) ||
      REQUIRED_LABELED_BLANK_RE.test(text))
  ) {
    addUnsupported(state, {
      code: 'UNBOUND_ORDINARY_PLACEHOLDER',
      partName: context.partName,
      path: nodePath,
      label: text,
      detail:
        'A visible placeholder is not bound to a Word field. Bind it to a supported control before certification.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }

  if (text && !hasFillableDescendant && !context.insideFieldContent) {
    addNode(state, {
      partName: context.partName,
      path: nodePath,
      kind: 'static',
      fieldId: null,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: hashText(text),
      bookmarkNames: bookmarkNames(node),
    });
  }

  walkNodes(
    childrenOf(node),
    nodePath,
    { ...context, containerText: text || null },
    state,
  );
}

interface DetectedOrdinaryPlaceholder {
  readonly binding: OrdinaryPlaceholderTokenBinding;
  readonly label: string;
}

function detectOrdinaryPlaceholderToken(
  paragraph: OrderedXmlNode,
  partName: string,
  state: CompilerState,
): DetectedOrdinaryPlaceholder | null {
  const part = state.bindingIndexes.get(partName);
  const indexedParagraph = part?.byNode.get(paragraph);
  if (!part || !indexedParagraph) return null;
  const textNodes = descendants(paragraph, 't');
  if (textNodes.length === 0) return null;
  const values = textNodes.map((textNode) => visibleText(textNode));
  const combined = values.join('');
  const matches = [...combined.matchAll(ORDINARY_PLACEHOLDER_GLOBAL_RE)];
  if (matches.length !== 1) return null;
  const match = matches[0]!;
  const token = match[0];
  const start = match.index;
  if (start === undefined) return null;
  const end = start + token.length;
  if (
    /^_+$/u.test(token) &&
    (/^[\p{L}\p{N}_]$/u.test(combined[start - 1] ?? '') ||
      /^[\p{L}\p{N}_]$/u.test(combined[end] ?? ''))
  ) {
    return null;
  }
  if (
    PLACEHOLDER_DELIMITER_FRAGMENT_RE.test(
      `${combined.slice(0, start)}${combined.slice(end)}`,
    )
  ) {
    return null;
  }
  const startPosition = textNodePosition(values, start, false);
  const endPosition = textNodePosition(values, end, true);
  if (!startPosition || !endPosition) return null;
  const binding = certifyOrdinaryPlaceholderTokenBinding({
    part,
    paragraph: indexedParagraph,
    startTextNodeIndex: startPosition.index,
    startOffset: startPosition.offset,
    endTextNodeIndex: endPosition.index,
    endOffset: endPosition.offset,
  });
  if (!binding) return null;
  const label = normalizeLabel(
    token
      .replace(/^<<|>>$/g, '')
      .replace(/^\[\[|\]\]$/g, '')
      .replace(/^\{\{|\}\}$/g, '')
      .replace(/^_+$/g, 'Blank field'),
  );
  return { binding, label: label || 'Template placeholder' };
}

function textNodePosition(
  values: readonly string[],
  target: number,
  preferPreviousBoundary: boolean,
): { index: number; offset: number } | null {
  let cursor = 0;
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index]!;
    const next = cursor + value.length;
    if (
      target < next ||
      (target === next &&
        (preferPreviousBoundary || index === values.length - 1))
    ) {
      return { index, offset: target - cursor };
    }
    cursor = next;
  }
  return null;
}

function createOrdinaryPlaceholderField(
  paragraph: OrderedXmlNode,
  paragraphPath: string,
  context: WalkContext,
  detected: DetectedOrdinaryPlaceholder,
  state: CompilerState,
): void {
  const kind = inferTextKind(detected.label);
  const fieldId = stableId(
    'ttf_',
    24,
    state.sourceSha256,
    context.partName,
    paragraphPath,
    detected.binding.tokenTextSha256,
  );
  const displayOrder = state.nextDisplayOrder++;
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: detected.label,
    labelSource: 'generated',
    displayOrder,
    detectionStatus: 'needs_confirmation',
    allowedOptions: [],
    rendererBinding: createCertifiedRendererBinding({
      fieldId,
      node: paragraph,
      context,
      bindingType: 'ordinary_placeholder',
      bindingProfile: ORDINARY_PLACEHOLDER_TOKEN_PROFILE,
      ordinaryPlaceholder: detected.binding,
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: null,
      sourceControlSha256: canonicalSha256(paragraph),
      originalContentSha256: detected.binding.tokenTextSha256,
      state,
    }),
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: inferCriticality(detected.label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: false,
  };
  pushField(field, context, state);
  addNode(
    state,
    {
      partName: context.partName,
      path: paragraphPath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(paragraph),
    },
    displayOrder,
  );
}

function processContentControl(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const properties = directChild(node, 'sdtPr');
  const content = directChild(node, 'sdtContent');
  if (!properties || !content) {
    addUnsupported(state, {
      code: 'MALFORMED_CONTENT_CONTROL',
      partName: context.partName,
      path: nodePath,
      label: null,
      detail:
        'A content control is missing its properties or content container.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
    if (content) {
      walkNodes(
        childrenOf(content),
        childPath(nodePath, content, node, state),
        context,
        state,
      );
    }
    return;
  }

  const contentPath = childPath(nodePath, content, node, state);
  const isRepeatingSection =
    descendants(properties, 'repeatingSection').length > 0;
  const isRepeatingItem =
    descendants(properties, 'repeatingSectionItem').length > 0;
  if (isRepeatingSection || isRepeatingItem) {
    const repeatPath = isRepeatingSection
      ? nodePath
      : (context.repeatAncestorPath ?? nodePath);
    if (isRepeatingSection && descendants(content, 'tbl').length === 0) {
      addUnsupported(state, {
        code: 'NON_TABLE_REPEATING_SECTION',
        partName: context.partName,
        path: nodePath,
        label: contentControlIdentity(properties).label,
        detail:
          'Only table-backed repeating sections are supported in Template Twin v1.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
    if (isRepeatingSection) {
      addUnsupported(state, {
        code: 'REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA',
        partName: context.partName,
        path: nodePath,
        label: contentControlIdentity(properties).label,
        detail:
          'Repeating Word sections are blocked in safe alpha because cloned rows cannot yet prove unique Word identifiers and stable clinical row alignment.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
    walkNodes(
      childrenOf(content),
      contentPath,
      { ...context, repeatAncestorPath: repeatPath },
      state,
    );
    return;
  }

  const identity = contentControlIdentity(properties);
  const dataBound = descendants(properties, 'dataBinding').length > 0;
  const dropdown = directChild(properties, 'dropDownList');
  const comboBox = directChild(properties, 'comboBox');
  const checkBox = descendants(properties, 'checkbox')[0];
  const date = directChild(properties, 'date');
  const plainText = directChild(properties, 'text');
  const richText = !dropdown && !comboBox && !checkBox && !date && !plainText;
  const structuredPlainText = Boolean(
    plainText &&
    (descendants(content, 'p').length > 1 ||
      descendants(content, 'numPr').length > 0),
  );
  const unsupportedType = [
    'picture',
    'group',
    'docPartObj',
    'bibliography',
    'citation',
    'equation',
  ].find((name) => descendants(properties, name).length > 0);

  if (unsupportedType) {
    addUnsupportedContentControl(
      state,
      context,
      nodePath,
      identity.label,
      'UNSUPPORTED_CONTENT_CONTROL',
      'This Word content-control type cannot be populated in Template Twin v1.',
    );
    walkNodes(
      childrenOf(content),
      contentPath,
      { ...context, insideFieldContent: true },
      state,
    );
    return;
  }

  let kind: TemplateField['kind'];
  let allowedOptions: TemplateField['allowedOptions'] = [];
  let ambiguousChoiceOptions = false;
  if (dropdown || comboBox) {
    const optionContainer = dropdown ?? comboBox!;
    allowedOptions = directChildren(optionContainer, 'listItem').map(
      (item, ordinal) => {
        const displayText =
          getAttribute(item, 'displayText') ??
          getAttribute(item, 'value') ??
          '';
        return {
          ordinal,
          displayText,
          value: getAttribute(item, 'value') ?? displayText,
        };
      },
    );
    if (
      allowedOptions.length === 0 ||
      allowedOptions.some((option) => !option.displayText)
    ) {
      addUnsupportedContentControl(
        state,
        context,
        nodePath,
        identity.label,
        'SELECT_OPTIONS_INVALID',
        'A native choice control has no complete, ordered option list.',
      );
      walkNodes(
        childrenOf(content),
        contentPath,
        { ...context, insideFieldContent: true },
        state,
      );
      return;
    }
    ambiguousChoiceOptions = hasDuplicateChoiceOptions(allowedOptions);
    if (ambiguousChoiceOptions) {
      addUnsupported(state, {
        code: 'AMBIGUOUS_SELECT_OPTIONS',
        partName: context.partName,
        path: nodePath,
        label: identity.label,
        detail:
          'A native choice control contains duplicate display text or values and requires physician review.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
    kind = 'single_select';
    if (comboBox) state.comboBoxes += 1;
  } else if (checkBox) {
    kind = 'checkbox';
  } else if (date) {
    kind = 'date';
  } else if (plainText || childrenOf(content).length > 0) {
    // Rich-text content controls have no dedicated type child in w:sdtPr.
    kind = inferTextKind(identity.label ?? context.containerText ?? '');
  } else {
    addUnsupportedContentControl(
      state,
      context,
      nodePath,
      identity.label,
      'UNRECOGNIZED_CONTENT_CONTROL',
      'The content-control type could not be identified deterministically.',
    );
    return;
  }

  if (dataBound) {
    addUnsupported(state, {
      code: 'DATA_BOUND_CONTENT_CONTROL',
      partName: context.partName,
      path: nodePath,
      label: identity.label,
      detail:
        'Data-bound controls require an explicit physician-approved replacement mapping.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }
  if (richText) {
    addUnsupported(state, {
      code: 'RICH_TEXT_CONTENT_CONTROL_UNSUPPORTED_SAFE_ALPHA',
      partName: context.partName,
      path: nodePath,
      label: identity.label,
      detail:
        'Rich-text Word controls are blocked in safe alpha because paragraphs, lists, and formatting cannot be flattened safely.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }
  if (structuredPlainText) {
    addUnsupported(state, {
      code: 'STRUCTURED_TEXT_CONTROL_UNSUPPORTED_SAFE_ALPHA',
      partName: context.partName,
      path: nodePath,
      label: identity.label,
      detail:
        'This text control contains multiple paragraphs or list structure and cannot be flattened safely in Template Twin safe alpha.',
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }

  const fieldId = stableId(
    'ttf_',
    24,
    state.sourceSha256,
    context.partName,
    nodePath,
    kind,
  );
  const label = chooseFieldLabel(
    identity,
    context.containerText,
    state.fields.length + 1,
  );
  const binding = createCertifiedRendererBinding({
    fieldId,
    node,
    context,
    bindingType: 'content_control',
    sdtId: trimNullable(identity.id, 80),
    tag: trimNullable(identity.tag, 240),
    alias: trimNullable(identity.alias, 240),
    legacyName: null,
    sourceControlSha256: canonicalSha256(node),
    originalContentSha256: canonicalSha256(content),
    state,
  });
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: label.label,
    labelSource: label.source,
    displayOrder: state.nextDisplayOrder++,
    detectionStatus:
      dataBound ||
      ambiguousChoiceOptions ||
      richText ||
      structuredPlainText ||
      context.repeatAncestorPath
        ? 'unsupported'
        : comboBox ||
            label.source === 'generated' ||
            label.source === 'same_container'
          ? 'needs_confirmation'
          : 'recognized',
    allowedOptions,
    rendererBinding: binding,
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: inferCriticality(label.label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    field.displayOrder,
  );

  walkNodes(
    childrenOf(content),
    contentPath,
    { ...context, insideFieldContent: true },
    state,
  );
}

function processLegacyField(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const formData = descendants(node, 'ffData')[0];
  if (!formData) return;
  const legacyName =
    descendants(formData, 'name')
      .map((name) => getAttribute(name, 'val'))
      .find(Boolean) ?? null;
  const dropdown = descendants(formData, 'ddList')[0];
  const checkbox = descendants(formData, 'checkBox')[0];
  const textInput = descendants(formData, 'textInput')[0];

  let kind: TemplateField['kind'];
  let allowedOptions: TemplateField['allowedOptions'] = [];
  let ambiguousChoiceOptions = false;
  if (dropdown) {
    kind = 'single_select';
    allowedOptions = descendants(dropdown, 'listEntry').map(
      (entry, ordinal) => {
        const value = getAttribute(entry, 'val') ?? '';
        return { ordinal, displayText: value, value };
      },
    );
    if (
      allowedOptions.length === 0 ||
      allowedOptions.some((option) => !option.value)
    ) {
      addUnsupportedLegacy(state, context, nodePath, legacyName);
      return;
    }
    ambiguousChoiceOptions = hasDuplicateChoiceOptions(allowedOptions);
    if (ambiguousChoiceOptions) {
      addUnsupported(state, {
        code: 'AMBIGUOUS_SELECT_OPTIONS',
        partName: context.partName,
        path: nodePath,
        label: trimNullable(legacyName, 240),
        detail:
          'A legacy choice field contains duplicate options and requires physician review.',
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
  } else if (checkbox) {
    kind = 'checkbox';
  } else if (textInput) {
    const typeValue = descendants(textInput, 'type')
      .map((type) => getAttribute(type, 'val')?.toLowerCase())
      .find(Boolean);
    kind = typeValue?.includes('number')
      ? 'number'
      : typeValue?.includes('date')
        ? 'date'
        : inferTextKind(legacyName ?? '');
  } else {
    addUnsupportedLegacy(state, context, nodePath, legacyName);
    return;
  }

  const label =
    normalizeLabel(legacyName ?? '') ||
    `Legacy field ${state.fields.length + 1}`;
  const labelSource = legacyName ? 'legacy_name' : 'generated';
  const fieldId = stableId(
    'ttf_',
    24,
    state.sourceSha256,
    context.partName,
    nodePath,
    kind,
  );
  const binding = createCertifiedRendererBinding({
    fieldId,
    node,
    context,
    bindingType: 'legacy_form_field',
    sdtId: null,
    tag: null,
    alias: null,
    legacyName: trimNullable(legacyName, 240),
    sourceControlSha256: canonicalSha256(node),
    originalContentSha256: canonicalSha256(formData),
    state,
  });
  const displayOrder = state.nextDisplayOrder++;
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: label.slice(0, 240),
    labelSource,
    displayOrder,
    detectionStatus:
      ambiguousChoiceOptions || context.repeatAncestorPath
        ? 'unsupported'
        : legacyName
          ? 'recognized'
          : 'needs_confirmation',
    allowedOptions,
    rendererBinding: binding,
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: inferCriticality(label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    displayOrder,
  );
}

function processTable(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  if (state.tables.length >= state.limits.maxTables) {
    failTemplateDocx('DOCUMENT_STRUCTURE_LIMIT_EXCEEDED');
  }
  const tableIndex = state.tableCountByPart.get(context.partName) ?? 0;
  state.tableCountByPart.set(context.partName, tableIndex + 1);
  const tableId = stableId(
    'ttb_',
    20,
    state.sourceSha256,
    context.partName,
    nodePath,
  );
  const rows = collectTableRows(
    node,
    nodePath,
    context.partName,
    context.repeatAncestorPath,
    state,
  );
  const repeatPrototypeRow = rows.findIndex(
    (row) => row.repeatAncestorPath !== null,
  );
  const kind: TemplateTable['kind'] =
    context.repeatAncestorPath || repeatPrototypeRow >= 0
      ? 'repeating_table'
      : 'fixed_table';
  const displayOrder = state.nextDisplayOrder++;
  const cells: TemplateTableCell[] = [];
  const table: TemplateTable = {
    tableId,
    partName: context.partName,
    path: nodePath,
    kind,
    displayOrder,
    gridColumnWidths: directChild(node, 'tblGrid')
      ? directChildren(directChild(node, 'tblGrid')!, 'gridCol').map((column) =>
          nonnegativeInteger(getAttribute(column, 'w')),
        )
      : [],
    rowCount: rows.length,
    repeatPrototypeRow:
      kind === 'repeating_table' ? Math.max(0, repeatPrototypeRow) : null,
    maxRows: MAX_TABLE_ROWS,
    cells,
  };
  state.tables.push(table);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId: null,
      tableId,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    displayOrder,
  );

  const tableHeaderLabels = new Map<number, string>();
  rows.forEach((row, rowIndex) => {
    let logicalColumnStart = 0;
    const rowCells = directChildrenWithPaths(row.node, row.path, 'tc', state);
    rowCells.forEach((cellLocation, cellIndex) => {
      const cell = cellLocation.node;
      const properties = directChild(cell, 'tcPr');
      const gridSpan = Math.max(
        1,
        positiveInteger(
          properties
            ? getAttribute(directChild(properties, 'gridSpan') ?? {}, 'val')
            : undefined,
        ),
      );
      const verticalMergeNode = properties
        ? directChild(properties, 'vMerge')
        : undefined;
      const verticalMerge: TemplateTableCell['verticalMerge'] =
        !verticalMergeNode
          ? 'none'
          : getAttribute(verticalMergeNode, 'val') === 'restart'
            ? 'restart'
            : 'continue';
      const fieldIds: string[] = [];
      const nestedTableCount = countNestedTables(cell);
      const cellText = normalizeLabel(visibleText(cell));
      cells.push({
        rowIndex,
        cellIndex,
        logicalColumnStart,
        gridSpan,
        verticalMerge,
        nestedTableCount,
        fieldIds,
        staticTextSha256: computeStaticXmlSha256([cell]),
      });

      const repeatAncestorPath =
        row.repeatAncestorPath ?? context.repeatAncestorPath;
      const cellContext: WalkContext = {
        ...context,
        table: {
          tableId,
          tableIndex,
          rowIndex,
          cellIndex,
          cellFieldIds: fieldIds,
          repeatAncestorPath,
        },
        repeatAncestorPath,
        containerText: cellText || context.containerText,
      };
      walkNodes(childrenOf(cell), cellLocation.path, cellContext, state);

      const hasBlankParagraphTabStopCandidate =
        containsBlankParagraphTabStopCandidate(cell);
      if (
        fieldIds.length === 0 &&
        (!cellText || hasBlankParagraphTabStopCandidate)
      ) {
        const leftLabel =
          cellIndex > 0
            ? normalizeLabel(visibleText(rowCells[cellIndex - 1]!.node))
            : '';
        const headerLabel = tableHeaderLabels.get(logicalColumnStart) ?? '';
        const admissionProfile = blankTableCellAdmissionProfile({
          cell,
          partName: context.partName,
          gridSpan,
          verticalMerge,
          nestedTableCount,
          state,
        });
        if (
          admissionProfile === null &&
          ((nestedTableCount === 0 && verticalMerge !== 'continue') ||
            hasBlankParagraphTabStopCandidate)
        ) {
          addUnsupported(state, {
            code: 'UNBOUND_COMPLEX_TABLE_CELL',
            partName: context.partName,
            path: cellLocation.path,
            label: leftLabel || headerLabel || null,
            detail:
              'A visually blank table cell contains a structure outside the certified safe-alpha table-cell profiles and cannot be bound safely.',
            clinicallyMaterial: true,
            blocksCertification: true,
          });
        } else if (admissionProfile !== null) {
          createAmbiguousTableCellField(
            cell,
            cellLocation.path,
            cellContext,
            admissionProfile === TAB_ONLY_BLANK_TABLE_CELL_PROFILE
              ? TAB_ONLY_BLANK_TABLE_CELL_PROFILE
              : undefined,
            leftLabel
              ? { label: leftLabel, source: 'left_cell' }
              : headerLabel
                ? { label: headerLabel, source: 'table_header' }
                : {
                    label: `Table ${tableIndex + 1}, row ${rowIndex + 1}, column ${logicalColumnStart + 1}`,
                    source: 'generated',
                  },
            state,
          );
        }
      }

      if (rowIndex === 0 && cellText) {
        for (
          let column = logicalColumnStart;
          column < logicalColumnStart + gridSpan;
          column += 1
        ) {
          tableHeaderLabels.set(column, cellText);
        }
      }
      logicalColumnStart += gridSpan;
    });
  });
}

type BlankTableCellAdmissionProfile =
  | 'PLAIN_BLANK_TABLE_CELL_V1'
  | typeof TAB_ONLY_BLANK_TABLE_CELL_PROFILE;

function blankTableCellAdmissionProfile(input: {
  cell: OrderedXmlNode;
  partName: string;
  gridSpan: number;
  verticalMerge: TemplateTableCell['verticalMerge'];
  nestedTableCount: number;
  state: CompilerState;
}): BlankTableCellAdmissionProfile | null {
  if (
    input.nestedTableCount === 0 &&
    input.verticalMerge !== 'continue' &&
    !blankCellHasUnsupportedStructure(input.cell)
  ) {
    return 'PLAIN_BLANK_TABLE_CELL_V1';
  }
  return isTabOnlyBlankTableCellV1(input)
    ? TAB_ONLY_BLANK_TABLE_CELL_PROFILE
    : null;
}

function blankCellHasUnsupportedStructure(cell: OrderedXmlNode): boolean {
  return (
    descendants(cell, 'p').length !== 1 ||
    ['br', 'cr', 'tab', 'drawing', 'pict', 'object'].some(
      (name) => descendants(cell, name).length > 0,
    )
  );
}

const TAB_STOP_PPR_SIMPLE_ON_OFF = new Set([
  'adjustRightInd',
  'autoSpaceDE',
  'autoSpaceDN',
  'contextualSpacing',
  'keepLines',
  'keepNext',
  'pageBreakBefore',
  'snapToGrid',
  'widowControl',
]);
const TAB_STOP_PPR_CHILDREN = new Set([
  ...TAB_STOP_PPR_SIMPLE_ON_OFF,
  'ind',
  'jc',
  'pStyle',
  'rPr',
  'spacing',
  'tabs',
]);
const TAB_STOP_RPR_CHILDREN = new Set([
  'b',
  'bCs',
  'color',
  'i',
  'iCs',
  'kern',
  'rFonts',
  'sz',
  'szCs',
  'u',
]);
function isTabOnlyBlankTableCellV1(input: {
  cell: OrderedXmlNode;
  partName: string;
  gridSpan: number;
  verticalMerge: TemplateTableCell['verticalMerge'];
  nestedTableCount: number;
  state: CompilerState;
}): boolean {
  if (
    input.gridSpan !== 1 ||
    input.verticalMerge !== 'none' ||
    input.nestedTableCount !== 0 ||
    !hasOnlyWhitespaceCharacterData(input.cell)
  ) {
    return false;
  }
  const part = input.state.bindingIndexes.get(input.partName);
  const cell = part?.byNode.get(input.cell);
  if (!part || !cell || !isIndexedWordElement(cell, 'tc')) return false;

  const directCellChildren = indexedDirectChildren(part, cell);
  const paragraphs = directCellChildren.filter((node) =>
    isIndexedWordElement(node, 'p'),
  );
  if (
    cell.visit.attributes.length > 0 ||
    paragraphs.length !== 1 ||
    directCellChildren.some(
      (node) =>
        !isIndexedWordElement(node, 'p') && !isIndexedWordElement(node, 'tcPr'),
    ) ||
    directCellChildren.filter((node) => isIndexedWordElement(node, 'tcPr'))
      .length > 1
  ) {
    return false;
  }
  const cellProperties = directCellChildren.find((node) =>
    isIndexedWordElement(node, 'tcPr'),
  );
  if (!validTabOnlyCellProperties(part, cellProperties)) return false;

  const paragraph = paragraphs[0]!;
  const paragraphChildren = indexedDirectChildren(part, paragraph);
  const paragraphProperties = paragraphChildren.filter((node) =>
    isIndexedWordElement(node, 'pPr'),
  );
  if (paragraphProperties.length !== 1 || paragraphChildren.length !== 1) {
    return false;
  }
  if (!validTabOnlyParagraphAttributes(paragraph)) return false;

  const pPr = paragraphProperties[0]!;
  if (pPr.visit.attributes.length > 0) return false;
  const propertyChildren = indexedDirectChildren(part, pPr);
  if (
    propertyChildren.some(
      (node) =>
        node.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
        !TAB_STOP_PPR_CHILDREN.has(node.visit.localName),
    )
  ) {
    return false;
  }
  const tabsNodes = propertyChildren.filter((node) =>
    isIndexedWordElement(node, 'tabs'),
  );
  if (
    tabsNodes.length !== 1 ||
    !uniqueExpandedChildNames(propertyChildren) ||
    !validTabStopDefinitions(part, tabsNodes[0]!)
  ) {
    return false;
  }

  for (const property of propertyChildren) {
    if (property === tabsNodes[0]) continue;
    if (TAB_STOP_PPR_SIMPLE_ON_OFF.has(property.visit.localName)) {
      if (!validOnOffProperty(property)) return false;
      continue;
    }
    if (property.visit.localName === 'jc') {
      if (!validJustificationProperty(property)) return false;
      continue;
    }
    if (property.visit.localName === 'rPr') {
      if (!validParagraphRunProperties(part, property)) return false;
      continue;
    }
    if (property.visit.localName === 'pStyle') {
      if (!validStringValueProperty(property)) return false;
      continue;
    }
    if (property.visit.localName === 'ind') {
      if (!validParagraphIndentation(property)) return false;
      continue;
    }
    if (property.visit.localName === 'spacing') {
      if (!validParagraphSpacing(property)) return false;
      continue;
    }
    return false;
  }
  return true;
}

function validTabOnlyCellProperties(
  part: IndexedBindingPart,
  tcPr: IndexedBindingNode | undefined,
): boolean {
  if (!tcPr) return true;
  if (tcPr.visit.attributes.length > 0) return false;
  const properties = indexedDirectChildren(part, tcPr);
  if (
    !uniqueExpandedChildNames(properties) ||
    properties.some(
      (property) =>
        property.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
        !['tcW', 'vAlign'].includes(property.visit.localName) ||
        indexedDirectChildren(part, property).length > 0,
    )
  ) {
    return false;
  }
  for (const property of properties) {
    if (property.visit.localName === 'tcW') {
      const width = exactExpandedAttribute(
        property.visit,
        WORDPROCESSINGML_NAMESPACE,
        'w',
      );
      const type = exactExpandedAttribute(
        property.visit,
        WORDPROCESSINGML_NAMESPACE,
        'type',
      );
      if (
        !width ||
        !/^(?:0|[1-9][0-9]{0,8})$/.test(width) ||
        !type ||
        !['auto', 'dxa', 'nil', 'pct'].includes(type) ||
        !attributesMatchAllowedNames(property, ['type', 'w'])
      ) {
        return false;
      }
      continue;
    }
    const alignment = exactExpandedAttribute(
      property.visit,
      WORDPROCESSINGML_NAMESPACE,
      'val',
    );
    if (
      !alignment ||
      !['bottom', 'center', 'top'].includes(alignment) ||
      !attributesMatchAllowedNames(property, ['val'])
    ) {
      return false;
    }
  }
  return true;
}

function validTabOnlyParagraphAttributes(
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

function hasOnlyWhitespaceCharacterData(node: OrderedXmlNode): boolean {
  const stack = [node];
  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const child of childrenOf(current)) {
      if (tagOf(child) === '#text') {
        if (!/^\s*$/u.test(String(child['#text'] ?? ''))) return false;
        continue;
      }
      stack.push(child);
    }
  }
  return true;
}

function containsBlankParagraphTabStopCandidate(cell: OrderedXmlNode): boolean {
  // This conservative candidate check intentionally uses local-name matching:
  // foreign namespace shadows are never admitted by the namespace-aware V1
  // classifier, but they must still keep the cell certification-blocked.
  return directChildren(cell, 'p').some(
    (paragraph) =>
      normalizeLabel(visibleText(paragraph)) === '' &&
      descendants(paragraph, 'tab').length > 0,
  );
}

function validTabStopDefinitions(
  part: IndexedBindingPart,
  tabs: IndexedBindingNode,
): boolean {
  if (tabs.visit.attributes.length > 0) return false;
  const stops = indexedDirectChildren(part, tabs);
  if (
    stops.length !== 1 ||
    stops.some((stop) => !isIndexedWordElement(stop, 'tab'))
  ) {
    return false;
  }
  for (const stop of stops) {
    if (indexedDirectChildren(part, stop).length > 0) return false;
    const value = exactExpandedAttribute(
      stop.visit,
      WORDPROCESSINGML_NAMESPACE,
      'val',
    );
    const position = exactExpandedAttribute(
      stop.visit,
      WORDPROCESSINGML_NAMESPACE,
      'pos',
    );
    if (
      value !== 'left' ||
      !position ||
      !/^(?:0|[1-9][0-9]{0,4})$/.test(position) ||
      Number(position) > 31_680 ||
      !attributesMatchAllowedNames(stop, ['pos', 'val'])
    ) {
      return false;
    }
  }
  return true;
}

function validParagraphRunProperties(
  part: IndexedBindingPart,
  rPr: IndexedBindingNode,
): boolean {
  if (rPr.visit.attributes.length > 0) return false;
  const properties = indexedDirectChildren(part, rPr);
  if (!uniqueExpandedChildNames(properties)) return false;
  for (const property of properties) {
    if (
      property.visit.namespaceUri === WORDPROCESSINGML_2010_NAMESPACE &&
      property.visit.localName === 'ligatures'
    ) {
      if (
        indexedDirectChildren(part, property).length > 0 ||
        exactExpandedAttribute(
          property.visit,
          WORDPROCESSINGML_2010_NAMESPACE,
          'val',
        ) !== 'none' ||
        !attributesMatchAllowedNames(
          property,
          ['val'],
          WORDPROCESSINGML_2010_NAMESPACE,
        )
      ) {
        return false;
      }
      continue;
    }
    if (
      property.visit.namespaceUri !== WORDPROCESSINGML_NAMESPACE ||
      !TAB_STOP_RPR_CHILDREN.has(property.visit.localName) ||
      indexedDirectChildren(part, property).length > 0
    ) {
      return false;
    }
    if (['b', 'bCs', 'i', 'iCs'].includes(property.visit.localName)) {
      if (!validOnOffProperty(property)) return false;
      continue;
    }
    const value = exactExpandedAttribute(
      property.visit,
      WORDPROCESSINGML_NAMESPACE,
      'val',
    );
    if (property.visit.localName === 'rFonts') {
      const allowed = [
        'ascii',
        'asciiTheme',
        'cs',
        'cstheme',
        'eastAsia',
        'eastAsiaTheme',
        'hAnsi',
        'hAnsiTheme',
      ];
      if (
        property.visit.attributes.length === 0 ||
        !attributesMatchAllowedNames(property, allowed) ||
        property.visit.attributes.some(
          (attribute) => !validBoundedOoxmlString(attribute.value),
        )
      ) {
        return false;
      }
      continue;
    }
    if (
      !attributesMatchAllowedNames(property, ['val']) ||
      value === undefined
    ) {
      return false;
    }
    if (property.visit.localName === 'color') {
      if (!/^(?:[0-9A-Fa-f]{6}|auto)$/.test(value)) return false;
      continue;
    }
    if (['kern', 'sz', 'szCs'].includes(property.visit.localName)) {
      if (!/^(?:0|[1-9][0-9]{0,3})$/.test(value) || Number(value) > 3276) {
        return false;
      }
      continue;
    }
    if (property.visit.localName === 'u') {
      if (
        ![
          'dash',
          'dashDotDotHeavy',
          'dashDotHeavy',
          'dashedHeavy',
          'dashLong',
          'dashLongHeavy',
          'dotDash',
          'dotDotDash',
          'dotted',
          'dottedHeavy',
          'double',
          'none',
          'single',
          'thick',
          'wave',
          'wavyDouble',
          'wavyHeavy',
          'words',
        ].includes(value)
      ) {
        return false;
      }
      continue;
    }
    return false;
  }
  return true;
}

function uniqueExpandedChildNames(
  nodes: readonly IndexedBindingNode[],
): boolean {
  const seen = new Set<string>();
  for (const node of nodes) {
    const key = `${node.visit.namespaceUri ?? ''}\0${node.visit.localName}`;
    if (seen.has(key)) return false;
    seen.add(key);
  }
  return true;
}

function validStringValueProperty(node: IndexedBindingNode): boolean {
  if (indexedChildElementCount(node) > 0) return false;
  const value = exactExpandedAttribute(
    node.visit,
    WORDPROCESSINGML_NAMESPACE,
    'val',
  );
  return (
    value !== undefined &&
    validBoundedOoxmlString(value) &&
    attributesMatchAllowedNames(node, ['val'])
  );
}

function validBoundedOoxmlString(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 240 &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function validParagraphIndentation(node: IndexedBindingNode): boolean {
  if (indexedChildElementCount(node) > 0) return false;
  const allowed = [
    'end',
    'endChars',
    'firstLine',
    'firstLineChars',
    'hanging',
    'hangingChars',
    'left',
    'leftChars',
    'right',
    'rightChars',
    'start',
    'startChars',
  ];
  if (
    node.visit.attributes.length === 0 ||
    !attributesMatchAllowedNames(node, allowed)
  ) {
    return false;
  }
  const values = new Map(
    node.visit.attributes.map((attribute) => [
      attribute.localName,
      attribute.value,
    ]),
  );
  if (
    (values.has('firstLine') && values.has('hanging')) ||
    (values.has('firstLineChars') && values.has('hangingChars'))
  ) {
    return false;
  }
  return [...values].every(([name, value]) =>
    name.endsWith('Chars')
      ? /^(?:0|[1-9][0-9]{0,4})$/.test(value)
      : /^-?(?:0|[1-9][0-9]{0,4})$/.test(value) &&
        Math.abs(Number(value)) <= 31_680,
  );
}

function validParagraphSpacing(node: IndexedBindingNode): boolean {
  if (indexedChildElementCount(node) > 0) return false;
  const allowed = [
    'after',
    'afterAutospacing',
    'afterLines',
    'before',
    'beforeAutospacing',
    'beforeLines',
    'line',
    'lineRule',
  ];
  if (
    node.visit.attributes.length === 0 ||
    !attributesMatchAllowedNames(node, allowed)
  ) {
    return false;
  }
  for (const attribute of node.visit.attributes) {
    if (attribute.localName === 'lineRule') {
      if (!['atLeast', 'auto', 'exact'].includes(attribute.value)) return false;
    } else if (
      ['afterAutospacing', 'beforeAutospacing'].includes(attribute.localName)
    ) {
      if (!['0', '1', 'false', 'off', 'on', 'true'].includes(attribute.value)) {
        return false;
      }
    } else if (!/^(?:0|[1-9][0-9]{0,5})$/.test(attribute.value)) {
      return false;
    }
  }
  return true;
}

function validOnOffProperty(node: IndexedBindingNode): boolean {
  if (indexedChildElementCount(node) > 0) return false;
  if (node.visit.attributes.length === 0) return true;
  const value = exactExpandedAttribute(
    node.visit,
    WORDPROCESSINGML_NAMESPACE,
    'val',
  );
  return (
    value !== undefined &&
    ['0', '1', 'false', 'off', 'on', 'true'].includes(value) &&
    attributesMatchAllowedNames(node, ['val'])
  );
}

function validJustificationProperty(node: IndexedBindingNode): boolean {
  if (indexedChildElementCount(node) > 0) return false;
  const value = exactExpandedAttribute(
    node.visit,
    WORDPROCESSINGML_NAMESPACE,
    'val',
  );
  return (
    value !== undefined &&
    [
      'both',
      'center',
      'distribute',
      'end',
      'highKashida',
      'left',
      'lowKashida',
      'mediumKashida',
      'numTab',
      'right',
      'start',
      'thaiDistribute',
    ].includes(value) &&
    attributesMatchAllowedNames(node, ['val'])
  );
}

function attributesMatchAllowedNames(
  node: IndexedBindingNode,
  allowedNames: readonly string[],
  namespaceUri = WORDPROCESSINGML_NAMESPACE,
): boolean {
  const allowed = new Set(allowedNames);
  const seen = new Set<string>();
  for (const attribute of node.visit.attributes) {
    if (
      attribute.namespaceUri !== namespaceUri ||
      !allowed.has(attribute.localName) ||
      seen.has(attribute.localName)
    ) {
      return false;
    }
    seen.add(attribute.localName);
  }
  return true;
}

function indexedDirectChildren(
  part: IndexedBindingPart,
  node: IndexedBindingNode,
): IndexedBindingNode[] {
  return childrenOf(node.node).flatMap((child) => {
    const indexed = part.byNode.get(child);
    return indexed ? [indexed] : [];
  });
}

function indexedChildElementCount(node: IndexedBindingNode): number {
  return childrenOf(node.node).filter((child) => {
    const tag = tagOf(child);
    return tag && tag !== '#text';
  }).length;
}

function createAmbiguousTableCellField(
  cell: OrderedXmlNode,
  cellPath: string,
  context: WalkContext,
  bindingProfile: RendererBinding['bindingProfile'] | undefined,
  label: { label: string; source: 'left_cell' | 'table_header' | 'generated' },
  state: CompilerState,
): void {
  const kind = inferTextKind(label.label);
  const fieldId = stableId(
    'ttf_',
    24,
    state.sourceSha256,
    context.partName,
    cellPath,
    kind,
  );
  const displayOrder = state.nextDisplayOrder++;
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: normalizeLabel(label.label),
    labelSource: label.source,
    displayOrder,
    detectionStatus: 'needs_confirmation',
    allowedOptions: [],
    rendererBinding: createCertifiedRendererBinding({
      fieldId,
      node: cell,
      context,
      bindingType: 'table_cell',
      bindingProfile,
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: null,
      sourceControlSha256: canonicalSha256(cell),
      originalContentSha256: canonicalSha256(cell),
      state,
    }),
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: inferCriticality(label.label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state);
  addNode(
    state,
    {
      partName: context.partName,
      path: cellPath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(cell),
    },
    displayOrder,
  );
}

function collectTableRows(
  table: OrderedXmlNode,
  tablePath: string,
  partName: string,
  inheritedRepeatPath: string | null,
  state: CompilerState,
): TableRowLocation[] {
  const rows: TableRowLocation[] = [];

  const walk = (
    nodes: OrderedXmlNode[],
    parentPath: string,
    repeatPath: string | null,
  ): void => {
    const siblingCounts = new Map<string, number>();
    for (const node of nodes) {
      const tag = tagOf(node);
      if (!tag || tag === '#text') continue;
      const index = siblingCounts.get(tag) ?? 0;
      siblingCounts.set(tag, index + 1);
      const nodePath = structuralPath(parentPath, tag, index, state);
      const local = localName(tag);
      if (local === 'tbl') continue;
      if (local === 'tr') {
        rows.push({ node, path: nodePath, repeatAncestorPath: repeatPath });
        continue;
      }
      let nextRepeatPath = repeatPath;
      if (local === 'sdt') {
        const properties = directChild(node, 'sdtPr');
        if (properties) {
          const isRepeatingSection =
            descendants(properties, 'repeatingSection').length > 0;
          const isRepeatingItem =
            descendants(properties, 'repeatingSectionItem').length > 0;
          if (isRepeatingSection || (isRepeatingItem && !nextRepeatPath)) {
            nextRepeatPath = nodePath;
          } else if (!isRepeatingItem && descendants(node, 'tr').length > 0) {
            addUnsupported(state, {
              code: 'ROW_CONTAINER_CONTENT_CONTROL',
              partName,
              path: nodePath,
              label: contentControlIdentity(properties).label,
              detail:
                'A non-repeating content control wraps a table row and requires physician review.',
              clinicallyMaterial: true,
              blocksCertification: true,
            });
          }
        }
      }
      walk(childrenOf(node), nodePath, nextRepeatPath);
    }
  };

  walk(childrenOf(table), tablePath, inheritedRepeatPath);
  return rows;
}

function directChildrenWithPaths(
  parent: OrderedXmlNode,
  parentPath: string,
  wantedLocalName: string,
  state: CompilerState,
): Array<{ node: OrderedXmlNode; path: string }> {
  const matches: Array<{ node: OrderedXmlNode; path: string }> = [];
  const siblingCounts = new Map<string, number>();
  for (const node of childrenOf(parent)) {
    const tag = tagOf(node);
    if (!tag || tag === '#text') continue;
    const index = siblingCounts.get(tag) ?? 0;
    siblingCounts.set(tag, index + 1);
    if (localName(tag) === wantedLocalName) {
      matches.push({
        node,
        path: structuralPath(parentPath, tag, index, state),
      });
    }
  }
  return matches;
}

function inspectDynamicField(
  instruction: string,
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const normalized = instruction.trim().toUpperCase();
  if (
    !normalized ||
    /^(?:PAGE|NUMPAGES|SECTION|SECTIONPAGES|DATE|TIME)\b/.test(normalized)
  ) {
    return;
  }
  if (!/^(?:IF|FILLIN|ASK)\b/.test(normalized) && !normalized.startsWith('='))
    return;

  addUnsupported(state, {
    code: 'DYNAMIC_FIELD_UNSUPPORTED',
    partName: context.partName,
    path: nodePath,
    label: null,
    detail:
      'A dynamic Word field requires physician review and is not fillable in Template Twin v1.',
    clinicallyMaterial: true,
    blocksCertification: true,
  });
  addNode(state, {
    partName: context.partName,
    path: nodePath,
    kind: 'conditional_block',
    fieldId: null,
    tableId: context.table?.tableId ?? null,
    staticTextSha256: canonicalSha256(node),
    bookmarkNames: bookmarkNames(node),
  });
}

function buildPartManifest(
  inspected: InspectedDocxPackage,
  parsedParts: ReadonlyMap<string, OrderedXmlNode[]>,
): TemplateDocPart[] {
  const headers = new Set(inspected.headerPartNames);
  const footers = new Set(inspected.footerPartNames);
  return [...inspected.zip.entries]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([partName, entry]) => {
      const sha256 = hashBytes(entry.bytes);
      const tree = parsedParts.get(partName);
      return {
        partName,
        contentType: inspected.contentTypes.get(partName)!,
        kind: partKind(partName, headers, footers),
        sha256,
        staticSha256: tree ? computeStaticXmlSha256(tree) : sha256,
        relationshipCount: inspected.relationshipCounts.get(partName) ?? 0,
      };
    });
}

/** Hashes OOXML structure while masking only content-control result bodies. */
export function computeStaticXmlSha256(tree: OrderedXmlNode[]): string {
  return canonicalSha256(tree.map(maskMutableContent));
}

function maskMutableContent(node: OrderedXmlNode): unknown {
  const tag = tagOf(node);
  const attributes = node[':@'] ? { ...node[':@'] } : undefined;
  const local = localName(tag);
  const rawValue = node[tag];
  let value: unknown;

  if (local === 'sdtContent') {
    value = [{ '#template-twin-mutable': '' }];
  } else if (Array.isArray(rawValue)) {
    value = (rawValue as OrderedXmlNode[]).map(maskMutableContent);
  } else {
    value = rawValue ?? '';
  }
  return attributes ? { [tag]: value, ':@': attributes } : { [tag]: value };
}

function pushField(
  field: TemplateField,
  context: WalkContext,
  state: CompilerState,
): void {
  if (state.fields.length >= state.limits.maxFields) {
    failTemplateDocx('DOCUMENT_STRUCTURE_LIMIT_EXCEEDED');
  }
  state.fields.push(field);
  context.table?.cellFieldIds.push(field.fieldId);
}

function addNode(
  state: CompilerState,
  input: Omit<TemplateDocNode, 'nodeId' | 'displayOrder'>,
  displayOrder = state.nextDisplayOrder++,
): void {
  if (state.nodes.length >= state.limits.maxNodes) {
    failTemplateDocx('DOCUMENT_STRUCTURE_LIMIT_EXCEEDED');
  }
  state.nodes.push({
    nodeId: stableId(
      'ttn_',
      20,
      state.sourceSha256,
      input.partName,
      input.path,
      input.kind,
    ),
    displayOrder,
    ...input,
  });
}

function addUnsupported(state: CompilerState, item: UnsupportedElement): void {
  const key = `${item.partName}\0${item.path}\0${item.code}`;
  if (state.unsupportedKeys.has(key)) return;
  state.unsupportedKeys.add(key);
  state.unsupported.push(item);
}

function addUnsupportedContentControl(
  state: CompilerState,
  context: WalkContext,
  path: string,
  label: string | null,
  code: string,
  detail: string,
): void {
  addUnsupported(state, {
    code,
    partName: context.partName,
    path,
    label,
    detail,
    clinicallyMaterial: true,
    blocksCertification: true,
  });
  addNode(state, {
    partName: context.partName,
    path,
    kind: 'unsupported',
    fieldId: null,
    tableId: context.table?.tableId ?? null,
    staticTextSha256: null,
    bookmarkNames: [],
  });
}

function addUnsupportedLegacy(
  state: CompilerState,
  context: WalkContext,
  path: string,
  label: string | null,
): void {
  addUnsupportedContentControl(
    state,
    context,
    path,
    trimNullable(label, 240),
    'UNSUPPORTED_LEGACY_FORM_FIELD',
    'A legacy Word form field could not be mapped safely.',
  );
}

function contentControlIdentity(properties: OrderedXmlNode): {
  alias: string | null;
  tag: string | null;
  id: string | null;
  label: string | null;
} {
  const alias = trimNullable(
    getAttribute(directChild(properties, 'alias') ?? {}, 'val'),
    240,
  );
  const tag = trimNullable(
    getAttribute(directChild(properties, 'tag') ?? {}, 'val'),
    240,
  );
  const id = trimNullable(
    getAttribute(directChild(properties, 'id') ?? {}, 'val'),
    80,
  );
  return { alias, tag, id, label: alias ?? tag };
}

function chooseFieldLabel(
  identity: ReturnType<typeof contentControlIdentity>,
  containerText: string | null,
  generatedOrdinal: number,
): { label: string; source: TemplateField['labelSource'] } {
  if (identity.alias) return { label: identity.alias, source: 'alias' };
  if (identity.tag) return { label: identity.tag, source: 'tag' };
  const normalizedContainer = normalizeLabel(containerText ?? '');
  if (normalizedContainer) {
    return { label: normalizedContainer, source: 'same_container' };
  }
  return { label: `Field ${generatedOrdinal}`, source: 'generated' };
}

function inferTextKind(label: string): TemplateField['kind'] {
  const normalized = label.toLowerCase();
  if (
    /\b(?:measurement|height|weight|length|width|diameter|temperature)\b/.test(
      normalized,
    )
  ) {
    return 'measurement';
  }
  if (/\b(?:number|count|score|quantity|age)\b/.test(normalized))
    return 'number';
  return 'narrative_text';
}

function inferCriticality(
  label: string,
  kind: TemplateField['kind'],
): TemplateField['criticality'] {
  const normalized = label.toLowerCase();
  if (
    /\b(?:medication|medicine|drug|dose|dosage|route|frequency)\b/.test(
      normalized,
    )
  ) {
    return 'medication';
  }
  if (/\b(?:allergy|allergies|adverse reaction)\b/.test(normalized))
    return 'allergy';
  if (/\b(?:laterality|side|left|right|bilateral)\b/.test(normalized))
    return 'laterality';
  if (
    kind === 'number' ||
    kind === 'measurement' ||
    /\bunit\b/.test(normalized)
  ) {
    return 'number_unit';
  }
  if (kind === 'date' || /\b(?:date|duration|onset)\b/.test(normalized)) {
    return 'date_duration';
  }
  return 'routine';
}

function hasDuplicateChoiceOptions(
  options: TemplateField['allowedOptions'],
): boolean {
  const displayTexts = new Set<string>();
  const values = new Set<string>();
  for (const option of options) {
    if (displayTexts.has(option.displayText) || values.has(option.value)) {
      return true;
    }
    displayTexts.add(option.displayText);
    values.add(option.value);
  }
  return false;
}

function childPath(
  parentPath: string,
  child: OrderedXmlNode,
  parent: OrderedXmlNode,
  state: CompilerState,
): string {
  const childTag = tagOf(child);
  let matchingIndex = 0;
  for (const candidate of childrenOf(parent)) {
    if (candidate === child) break;
    if (tagOf(candidate) === childTag) matchingIndex += 1;
  }
  return structuralPath(parentPath, childTag, matchingIndex, state);
}

function structuralPath(
  parentPath: string,
  tag: string,
  siblingIndex: number,
  state: CompilerState,
): string {
  const value = `${parentPath}/${tag}[${siblingIndex}]`;
  if (value.length > state.limits.maxStructuralPathLength) {
    failTemplateDocx('DOCUMENT_STRUCTURE_LIMIT_EXCEEDED');
  }
  return value;
}

function bookmarkNames(node: OrderedXmlNode): string[] {
  return [
    ...new Set(
      descendants(node, 'bookmarkStart')
        .map((bookmark) => getAttribute(bookmark, 'name'))
        .filter((name): name is string => Boolean(name) && name !== '_GoBack')
        .map((name) => name.slice(0, 240)),
    ),
  ];
}

function countNestedTables(cell: OrderedXmlNode): number {
  return descendants(cell, 'tbl').length;
}

function partKind(
  partName: string,
  headers: ReadonlySet<string>,
  footers: ReadonlySet<string>,
): TemplateDocPart['kind'] {
  if (partName === 'word/document.xml') return 'document';
  if (headers.has(partName)) return 'header';
  if (footers.has(partName)) return 'footer';
  if (/^word\/styles[^/]*\.xml$/i.test(partName)) return 'styles';
  if (/^word\/numbering[^/]*\.xml$/i.test(partName)) return 'numbering';
  if (partName.endsWith('.rels')) return 'relationships';
  if (/^word\/media\//i.test(partName)) return 'media';
  return 'other';
}

function stableId(prefix: string, length: number, ...parts: string[]): string {
  return `${prefix}${createHash('sha256').update(parts.join('\0'), 'utf8').digest('hex').slice(0, length)}`;
}

function hashBytes(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function hashText(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function normalizeLabel(value: string): string {
  return value.replace(/\s+/g, ' ').trim().slice(0, 240);
}

function trimNullable(
  value: string | null | undefined,
  maxLength: number,
): string | null {
  const normalized = value?.trim();
  return normalized ? normalized.slice(0, maxLength) : null;
}

function nonnegativeInteger(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function positiveInteger(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}
