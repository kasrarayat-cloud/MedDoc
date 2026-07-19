import { createHash } from 'node:crypto';

import type { InspectedDocxPackage } from '@/lib/note-template-docx';
import {
  MARKUP_COMPATIBILITY_NAMESPACE,
  OPC_RELATIONSHIPS_NAMESPACE,
  WORDPROCESSINGML_NAMESPACE,
  WORDPROCESSINGML_2010_NAMESPACE,
  WORDPROCESSINGML_2012_NAMESPACE,
  childrenOf,
  decodeXmlScalar,
  expandedXmlVisits,
  parseOrderedXml,
  tagOf,
  type ExpandedXmlVisit,
} from '@/lib/note-template-docx/xml';

import { canonicalSha256 } from './canonical';

export const TEMPLATE_TWIN_AUXILIARY_PROFILE =
  'template-twin-word-auxiliary-safe-v1' as const;

const MAX_AUXILIARY_PART_BYTES = 256 * 1024;
const MAX_AUXILIARY_AGGREGATE_BYTES = 512 * 1024;
const WORD_RELATIONSHIP_BASE =
  'http://schemas.openxmlformats.org/officeDocument/2006/relationships/';
const OFFICE_MATH_NAMESPACE =
  'http://schemas.openxmlformats.org/officeDocument/2006/math';

type ExpandedName = readonly [namespaceUri: string | null, localName: string];
type AuxiliaryElementSpec = readonly [
  namespaceUri: string,
  localName: string,
  attributes: readonly ExpandedName[],
];
type AuxiliaryEdgeSpec = readonly [
  parentNamespaceUri: string,
  parentLocalName: string,
  childNamespaceUri: string,
  childLocalName: string,
];

interface AuxiliaryXmlProfile {
  readonly rootNamespace: string;
  readonly rootLocalName: string;
  readonly elements: ReadonlyMap<string, ReadonlySet<string>>;
  readonly edges: ReadonlySet<string>;
}

const W = WORDPROCESSINGML_NAMESPACE;
const M = OFFICE_MATH_NAMESPACE;
const W14 = WORDPROCESSINGML_2010_NAMESPACE;
const W15 = WORDPROCESSINGML_2012_NAMESPACE;
const MC = MARKUP_COMPATIBILITY_NAMESPACE;
const NONE: null = null;

const attr = (namespaceUri: string | null, localName: string): ExpandedName => [
  namespaceUri,
  localName,
];
const element = (
  namespaceUri: string,
  localName: string,
  attributes: readonly ExpandedName[] = [],
): AuxiliaryElementSpec => [namespaceUri, localName, attributes];
const edge = (
  parentNamespaceUri: string,
  parentLocalName: string,
  childNamespaceUri: string,
  childLocalName: string,
): AuxiliaryEdgeSpec => [
  parentNamespaceUri,
  parentLocalName,
  childNamespaceUri,
  childLocalName,
];
const wAttr = (localName: string): ExpandedName => attr(W, localName);
const mAttr = (localName: string): ExpandedName => attr(M, localName);

function expandedNameKey(
  namespaceUri: string | null,
  localName: string,
): string {
  return `${namespaceUri ?? '<none>'}\u0000${localName}`;
}

function edgeKey(
  parentNamespaceUri: string,
  parentLocalName: string,
  childNamespaceUri: string,
  childLocalName: string,
): string {
  return `${expandedNameKey(parentNamespaceUri, parentLocalName)}\u0001${expandedNameKey(childNamespaceUri, childLocalName)}`;
}

function xmlProfile(input: {
  root: readonly [namespaceUri: string, localName: string];
  elements: readonly AuxiliaryElementSpec[];
  edges: readonly AuxiliaryEdgeSpec[];
}): AuxiliaryXmlProfile {
  const elements = new Map<string, ReadonlySet<string>>();
  for (const [namespaceUri, localName, attributes] of input.elements) {
    const key = expandedNameKey(namespaceUri, localName);
    if (elements.has(key)) throw new Error(`Duplicate auxiliary profile element: ${key}`);
    elements.set(
      key,
      new Set(
        attributes.map(([attributeNamespace, attributeLocalName]) =>
          expandedNameKey(attributeNamespace, attributeLocalName),
        ),
      ),
    );
  }
  return {
    rootNamespace: input.root[0],
    rootLocalName: input.root[1],
    elements,
    edges: new Set(
      input.edges.map(([parentNs, parentName, childNs, childName]) =>
        edgeKey(parentNs, parentName, childNs, childName),
      ),
    ),
  };
}

const ROOT_ATTRIBUTES = [attr(MC, 'Ignorable')] as const;
const WORD_VALUE = [wAttr('val')] as const;

/**
 * This is intentionally a structural allowlist, not a schema-shaped wildcard.
 * It describes only the standard Word structures independently observed in
 * the six accepted WM IOV glossary parts. A new element, attribute, namespace,
 * or parent/child placement must be reviewed and versioned before admission.
 */
const GLOSSARY_DOCUMENT_PROFILE = xmlProfile({
  root: [W, 'glossaryDocument'],
  elements: [
    element(W, 'glossaryDocument', ROOT_ATTRIBUTES),
    element(W, 'docParts'),
    element(W, 'docPart'),
    element(W, 'docPartPr'),
    element(W, 'name', WORD_VALUE),
    element(W, 'category'),
    element(W, 'gallery', WORD_VALUE),
    element(W, 'types'),
    element(W, 'type', WORD_VALUE),
    element(W, 'behaviors'),
    element(W, 'behavior', WORD_VALUE),
    element(W, 'guid', WORD_VALUE),
    element(W, 'docPartBody'),
    element(W, 'p', [wAttr('rsidP'), wAttr('rsidR'), wAttr('rsidRDefault')]),
    element(W, 'pPr'),
    element(W, 'pStyle', WORD_VALUE),
    element(W, 'r', [wAttr('rsidRPr')]),
    element(W, 'rPr'),
    element(W, 'rFonts', [wAttr('ascii'), wAttr('cs'), wAttr('hAnsi')]),
    element(W, 'rStyle', WORD_VALUE),
    element(W, 'sz', WORD_VALUE),
    element(W, 'szCs', WORD_VALUE),
    element(W, 't'),
  ],
  edges: [
    edge(W, 'glossaryDocument', W, 'docParts'),
    edge(W, 'docParts', W, 'docPart'),
    edge(W, 'docPart', W, 'docPartPr'),
    edge(W, 'docPart', W, 'docPartBody'),
    edge(W, 'docPartPr', W, 'name'),
    edge(W, 'docPartPr', W, 'category'),
    edge(W, 'docPartPr', W, 'types'),
    edge(W, 'docPartPr', W, 'behaviors'),
    edge(W, 'docPartPr', W, 'guid'),
    edge(W, 'category', W, 'name'),
    edge(W, 'category', W, 'gallery'),
    edge(W, 'types', W, 'type'),
    edge(W, 'behaviors', W, 'behavior'),
    edge(W, 'docPartBody', W, 'p'),
    edge(W, 'p', W, 'pPr'),
    edge(W, 'p', W, 'r'),
    edge(W, 'pPr', W, 'pStyle'),
    edge(W, 'r', W, 'rPr'),
    edge(W, 'r', W, 't'),
    edge(W, 'rPr', W, 'rFonts'),
    edge(W, 'rPr', W, 'rStyle'),
    edge(W, 'rPr', W, 'sz'),
    edge(W, 'rPr', W, 'szCs'),
  ],
});

const SETTINGS_PROFILE = xmlProfile({
  root: [W, 'settings'],
  elements: [
    element(W, 'settings', ROOT_ATTRIBUTES),
    element(W, 'view', WORD_VALUE),
    element(W, 'defaultTabStop', WORD_VALUE),
    element(W, 'characterSpacingControl', WORD_VALUE),
    element(W, 'compat'),
    element(W, 'useFELayout'),
    element(W, 'compatSetting', [wAttr('name'), wAttr('uri'), wAttr('val')]),
    element(M, 'mathPr'),
    element(M, 'mathFont', [mAttr('val')]),
    element(M, 'brkBin', [mAttr('val')]),
    element(M, 'brkBinSub', [mAttr('val')]),
    element(M, 'smallFrac', [mAttr('val')]),
    element(M, 'dispDef'),
    element(M, 'lMargin', [mAttr('val')]),
    element(M, 'rMargin', [mAttr('val')]),
    element(M, 'defJc', [mAttr('val')]),
    element(M, 'wrapIndent', [mAttr('val')]),
    element(M, 'intLim', [mAttr('val')]),
    element(M, 'naryLim', [mAttr('val')]),
    element(W, 'themeFontLang', WORD_VALUE),
    element(W, 'clrSchemeMapping', [
      wAttr('accent1'),
      wAttr('accent2'),
      wAttr('accent3'),
      wAttr('accent4'),
      wAttr('accent5'),
      wAttr('accent6'),
      wAttr('bg1'),
      wAttr('bg2'),
      wAttr('followedHyperlink'),
      wAttr('hyperlink'),
      wAttr('t1'),
      wAttr('t2'),
    ]),
    element(W, 'decimalSymbol', WORD_VALUE),
    element(W, 'listSeparator', WORD_VALUE),
    element(W, 'rsids'),
    element(W, 'rsidRoot', WORD_VALUE),
    element(W, 'rsid', WORD_VALUE),
    element(W15, 'chartTrackingRefBased'),
  ],
  edges: [
    edge(W, 'settings', W, 'view'),
    edge(W, 'settings', W, 'defaultTabStop'),
    edge(W, 'settings', W, 'characterSpacingControl'),
    edge(W, 'settings', W, 'compat'),
    edge(W, 'settings', M, 'mathPr'),
    edge(W, 'settings', W, 'themeFontLang'),
    edge(W, 'settings', W, 'clrSchemeMapping'),
    edge(W, 'settings', W, 'decimalSymbol'),
    edge(W, 'settings', W, 'listSeparator'),
    edge(W, 'settings', W, 'rsids'),
    edge(W, 'settings', W15, 'chartTrackingRefBased'),
    edge(W, 'compat', W, 'useFELayout'),
    edge(W, 'compat', W, 'compatSetting'),
    edge(W, 'rsids', W, 'rsidRoot'),
    edge(W, 'rsids', W, 'rsid'),
    edge(M, 'mathPr', M, 'mathFont'),
    edge(M, 'mathPr', M, 'brkBin'),
    edge(M, 'mathPr', M, 'brkBinSub'),
    edge(M, 'mathPr', M, 'smallFrac'),
    edge(M, 'mathPr', M, 'dispDef'),
    edge(M, 'mathPr', M, 'lMargin'),
    edge(M, 'mathPr', M, 'rMargin'),
    edge(M, 'mathPr', M, 'defJc'),
    edge(M, 'mathPr', M, 'wrapIndent'),
    edge(M, 'mathPr', M, 'intLim'),
    edge(M, 'mathPr', M, 'naryLim'),
  ],
});

const STYLES_PROFILE = xmlProfile({
  root: [W, 'styles'],
  elements: [
    element(W, 'styles', ROOT_ATTRIBUTES),
    element(W, 'docDefaults'),
    element(W, 'rPrDefault'),
    element(W, 'rPr'),
    element(W, 'rFonts', [
      wAttr('asciiTheme'),
      wAttr('cstheme'),
      wAttr('eastAsiaTheme'),
      wAttr('hAnsiTheme'),
    ]),
    element(W, 'lang', [wAttr('bidi'), wAttr('eastAsia'), wAttr('val')]),
    element(W, 'color', WORD_VALUE),
    element(W, 'sz', WORD_VALUE),
    element(W, 'szCs', WORD_VALUE),
    element(W, 'kern', WORD_VALUE),
    element(W14, 'ligatures', [attr(W14, 'val')]),
    element(W, 'pPrDefault'),
    element(W, 'pPr'),
    element(W, 'spacing', [wAttr('after'), wAttr('line'), wAttr('lineRule')]),
    element(W, 'latentStyles', [
      wAttr('count'),
      wAttr('defLockedState'),
      wAttr('defQFormat'),
      wAttr('defSemiHidden'),
      wAttr('defUIPriority'),
      wAttr('defUnhideWhenUsed'),
    ]),
    element(W, 'lsdException', [
      wAttr('name'),
      wAttr('qFormat'),
      wAttr('semiHidden'),
      wAttr('uiPriority'),
      wAttr('unhideWhenUsed'),
    ]),
    element(W, 'style', [
      wAttr('customStyle'),
      wAttr('default'),
      wAttr('styleId'),
      wAttr('type'),
    ]),
    element(W, 'name', WORD_VALUE),
    element(W, 'basedOn', WORD_VALUE),
    element(W, 'uiPriority', WORD_VALUE),
    element(W, 'semiHidden'),
    element(W, 'unhideWhenUsed'),
    element(W, 'qFormat'),
    element(W, 'rsid', WORD_VALUE),
    element(W, 'ind', [wAttr('left')]),
    element(W, 'contextualSpacing'),
    element(W, 'tblPr'),
    element(W, 'tblInd', [wAttr('type'), wAttr('w')]),
    element(W, 'tblCellMar'),
    element(W, 'top', [wAttr('type'), wAttr('w')]),
    element(W, 'left', [wAttr('type'), wAttr('w')]),
    element(W, 'bottom', [wAttr('type'), wAttr('w')]),
    element(W, 'right', [wAttr('type'), wAttr('w')]),
  ],
  edges: [
    edge(W, 'styles', W, 'docDefaults'),
    edge(W, 'styles', W, 'latentStyles'),
    edge(W, 'styles', W, 'style'),
    edge(W, 'docDefaults', W, 'rPrDefault'),
    edge(W, 'docDefaults', W, 'pPrDefault'),
    edge(W, 'rPrDefault', W, 'rPr'),
    edge(W, 'pPrDefault', W, 'pPr'),
    edge(W, 'latentStyles', W, 'lsdException'),
    edge(W, 'style', W, 'name'),
    edge(W, 'style', W, 'basedOn'),
    edge(W, 'style', W, 'uiPriority'),
    edge(W, 'style', W, 'semiHidden'),
    edge(W, 'style', W, 'unhideWhenUsed'),
    edge(W, 'style', W, 'qFormat'),
    edge(W, 'style', W, 'rsid'),
    edge(W, 'style', W, 'rPr'),
    edge(W, 'style', W, 'pPr'),
    edge(W, 'style', W, 'tblPr'),
    edge(W, 'rPr', W, 'rFonts'),
    edge(W, 'rPr', W, 'lang'),
    edge(W, 'rPr', W, 'color'),
    edge(W, 'rPr', W, 'sz'),
    edge(W, 'rPr', W, 'szCs'),
    edge(W, 'rPr', W, 'kern'),
    edge(W, 'rPr', W14, 'ligatures'),
    edge(W, 'pPr', W, 'spacing'),
    edge(W, 'pPr', W, 'ind'),
    edge(W, 'pPr', W, 'contextualSpacing'),
    edge(W, 'tblPr', W, 'tblInd'),
    edge(W, 'tblPr', W, 'tblCellMar'),
    edge(W, 'tblCellMar', W, 'top'),
    edge(W, 'tblCellMar', W, 'left'),
    edge(W, 'tblCellMar', W, 'bottom'),
    edge(W, 'tblCellMar', W, 'right'),
  ],
});

const WEB_SETTINGS_PROFILE = xmlProfile({
  root: [W, 'webSettings'],
  elements: [
    element(W, 'webSettings', ROOT_ATTRIBUTES),
    element(W, 'allowPNG'),
    element(W, 'optimizeForBrowser'),
  ],
  edges: [
    edge(W, 'webSettings', W, 'allowPNG'),
    edge(W, 'webSettings', W, 'optimizeForBrowser'),
  ],
});

const FONT_TABLE_PROFILE = xmlProfile({
  root: [W, 'fonts'],
  elements: [
    element(W, 'fonts', ROOT_ATTRIBUTES),
    element(W, 'font', [wAttr('name')]),
    element(W, 'panose1', WORD_VALUE),
    element(W, 'charset', WORD_VALUE),
    element(W, 'family', WORD_VALUE),
    element(W, 'pitch', WORD_VALUE),
    element(W, 'sig', [
      wAttr('csb0'),
      wAttr('csb1'),
      wAttr('usb0'),
      wAttr('usb1'),
      wAttr('usb2'),
      wAttr('usb3'),
    ]),
  ],
  edges: [
    edge(W, 'fonts', W, 'font'),
    edge(W, 'font', W, 'panose1'),
    edge(W, 'font', W, 'charset'),
    edge(W, 'font', W, 'family'),
    edge(W, 'font', W, 'pitch'),
    edge(W, 'font', W, 'sig'),
  ],
});

const RELATIONSHIPS_PROFILE = xmlProfile({
  root: [OPC_RELATIONSHIPS_NAMESPACE, 'Relationships'],
  elements: [
    element(OPC_RELATIONSHIPS_NAMESPACE, 'Relationships'),
    element(OPC_RELATIONSHIPS_NAMESPACE, 'Relationship', [
      attr(NONE, 'Id'),
      attr(NONE, 'Target'),
      attr(NONE, 'Type'),
    ]),
  ],
  edges: [
    edge(
      OPC_RELATIONSHIPS_NAMESPACE,
      'Relationships',
      OPC_RELATIONSHIPS_NAMESPACE,
      'Relationship',
    ),
  ],
});

const SAFE_IGNORABLE_EXTENSION_NAMESPACES = new Set([
  WORDPROCESSINGML_2010_NAMESPACE,
  WORDPROCESSINGML_2012_NAMESPACE,
  'http://schemas.microsoft.com/office/word/2015/wordml/symex',
  'http://schemas.microsoft.com/office/word/2016/wordml/cid',
  'http://schemas.microsoft.com/office/word/2018/wordml',
  'http://schemas.microsoft.com/office/word/2018/wordml/cex',
  'http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash',
  'http://schemas.microsoft.com/office/word/2023/wordml/word16du',
  'http://schemas.microsoft.com/office/word/2024/wordml/sdtformatlock',
  'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
]);

const XML_PROFILES = new Map<string, AuxiliaryXmlProfile>([
  ['word/glossary/document.xml', GLOSSARY_DOCUMENT_PROFILE],
  ['word/glossary/settings.xml', SETTINGS_PROFILE],
  ['word/glossary/styles.xml', STYLES_PROFILE],
  ['word/glossary/webSettings.xml', WEB_SETTINGS_PROFILE],
  ['word/glossary/fontTable.xml', FONT_TABLE_PROFILE],
  ['word/glossary/_rels/document.xml.rels', RELATIONSHIPS_PROFILE],
]);

const STANDARD_PARTS = new Map<
  string,
  { contentType: string; rootNamespace: string; rootLocalName: string }
>([
  [
    'word/glossary/document.xml',
    {
      contentType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document.glossary+xml',
      rootNamespace: WORDPROCESSINGML_NAMESPACE,
      rootLocalName: 'glossaryDocument',
    },
  ],
  [
    'word/glossary/settings.xml',
    {
      contentType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml',
      rootNamespace: WORDPROCESSINGML_NAMESPACE,
      rootLocalName: 'settings',
    },
  ],
  [
    'word/glossary/styles.xml',
    {
      contentType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml',
      rootNamespace: WORDPROCESSINGML_NAMESPACE,
      rootLocalName: 'styles',
    },
  ],
  [
    'word/glossary/webSettings.xml',
    {
      contentType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml',
      rootNamespace: WORDPROCESSINGML_NAMESPACE,
      rootLocalName: 'webSettings',
    },
  ],
  [
    'word/glossary/fontTable.xml',
    {
      contentType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml',
      rootNamespace: WORDPROCESSINGML_NAMESPACE,
      rootLocalName: 'fonts',
    },
  ],
]);

const RELATIONSHIP_PART = 'word/glossary/_rels/document.xml.rels';
const RELATIONSHIP_CONTENT_TYPE =
  'application/vnd.openxmlformats-package.relationships+xml';

const CHILD_RELATIONSHIPS = new Map([
  ['word/glossary/settings.xml', `${WORD_RELATIONSHIP_BASE}settings`],
  ['word/glossary/styles.xml', `${WORD_RELATIONSHIP_BASE}styles`],
  ['word/glossary/webSettings.xml', `${WORD_RELATIONSHIP_BASE}webSettings`],
  ['word/glossary/fontTable.xml', `${WORD_RELATIONSHIP_BASE}fontTable`],
]);

const GLOSSARY_DOCUMENT_RELATIONSHIP =
  `${WORD_RELATIONSHIP_BASE}glossaryDocument`;

const BLOCKED_WORD_ELEMENTS = new Set([
  'altChunk',
  'customXml',
  'dataBinding',
  'del',
  'delText',
  'fldChar',
  'fldSimple',
  'ins',
  'instrText',
  'moveFrom',
  'moveFromRangeEnd',
  'moveFromRangeStart',
  'moveTo',
  'moveToRangeEnd',
  'moveToRangeStart',
  'object',
  'pict',
]);

export class TemplateTwinAuxiliaryPartUnsupportedError extends Error {
  readonly code = 'TEMPLATE_TWIN_AUXILIARY_PART_UNSUPPORTED';

  constructor(readonly reasonCode: string) {
    super(
      `${reasonCode}: This Word building-block part cannot be fully inspected by the current safe profile.`,
    );
    this.name = 'TemplateTwinAuxiliaryPartUnsupportedError';
  }
}

export interface TemplateTwinAuxiliaryPartEvidence {
  readonly partName: string;
  readonly contentType: string;
  readonly sizeBytes: number;
  readonly sha256: string;
  readonly relationshipCount: number;
}

export interface TemplateTwinAuxiliaryManifest {
  readonly profileVersion: typeof TEMPLATE_TWIN_AUXILIARY_PROFILE;
  readonly parts: readonly TemplateTwinAuxiliaryPartEvidence[];
  readonly manifestSha256: string;
}

export function isStandardWordAuxiliaryPartName(partName: string): boolean {
  return STANDARD_PARTS.has(partName) || partName === RELATIONSHIP_PART;
}

export function inspectStandardWordAuxiliaryParts(
  inspected: InspectedDocxPackage,
): TemplateTwinAuxiliaryManifest {
  const glossaryNames = [...inspected.zip.entries.keys()]
    .filter((partName) => partName.startsWith('word/glossary/'))
    .sort();
  if (glossaryNames.length === 0) return emptyAuxiliaryManifest();

  if (
    glossaryNames.length > STANDARD_PARTS.size + 1 ||
    glossaryNames.some((partName) => !isStandardWordAuxiliaryPartName(partName))
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_PART_FAMILY_UNSUPPORTED',
    );
  }
  if (!glossaryNames.includes('word/glossary/document.xml')) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_GLOSSARY_ROOT_MISSING',
    );
  }

  const totalBytes = glossaryNames.reduce(
    (total, partName) =>
      total + (inspected.zip.entries.get(partName)?.bytes.byteLength ?? 0),
    0,
  );
  if (totalBytes > MAX_AUXILIARY_AGGREGATE_BYTES) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_RESOURCE_LIMIT_EXCEEDED',
    );
  }

  const manifestParts: TemplateTwinAuxiliaryPartEvidence[] = [];
  for (const partName of glossaryNames) {
    const entry = inspected.zip.entries.get(partName);
    if (!entry || entry.bytes.byteLength > MAX_AUXILIARY_PART_BYTES) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_RESOURCE_LIMIT_EXCEEDED',
      );
    }
    const expected = STANDARD_PARTS.get(partName);
    const expectedContentType = expected?.contentType ?? RELATIONSHIP_CONTENT_TYPE;
    if (inspected.contentTypes.get(partName) !== expectedContentType) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_CONTENT_TYPE_INVALID',
      );
    }
    const profile = XML_PROFILES.get(partName);
    if (!profile) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_PART_FAMILY_UNSUPPORTED',
      );
    }
    assertAuxiliaryXmlProfile(inspected, partName, profile);
    manifestParts.push({
      partName,
      contentType: expectedContentType,
      sizeBytes: entry.bytes.byteLength,
      sha256: createHash('sha256').update(entry.bytes).digest('hex'),
      relationshipCount: inspected.relationshipCounts.get(partName) ?? 0,
    });
  }

  assertAuxiliaryRelationshipGraph(inspected, new Set(glossaryNames));
  const canonical = {
    profileVersion: TEMPLATE_TWIN_AUXILIARY_PROFILE,
    parts: manifestParts,
  };
  return { ...canonical, manifestSha256: canonicalSha256(canonical) };
}

export function assertStandardWordAuxiliaryPartsUnchanged(input: {
  certified: TemplateTwinAuxiliaryManifest;
  completed: InspectedDocxPackage;
}): void {
  const completed = inspectStandardWordAuxiliaryParts(input.completed);
  if (
    input.certified.profileVersion !== TEMPLATE_TWIN_AUXILIARY_PROFILE ||
    input.certified.manifestSha256 !== completed.manifestSha256 ||
    canonicalSha256({
      profileVersion: input.certified.profileVersion,
      parts: input.certified.parts,
    }) !== input.certified.manifestSha256
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_STATIC_MUTATION_DETECTED',
    );
  }
}

function emptyAuxiliaryManifest(): TemplateTwinAuxiliaryManifest {
  const value = {
    profileVersion: TEMPLATE_TWIN_AUXILIARY_PROFILE,
    parts: [] as readonly TemplateTwinAuxiliaryPartEvidence[],
  };
  return { ...value, manifestSha256: canonicalSha256(value) };
}

function assertAuxiliaryXmlProfile(
  inspected: InspectedDocxPackage,
  partName: string,
  profile: AuxiliaryXmlProfile,
): void {
  const entry = inspected.zip.entries.get(partName)!;
  const visits = expandedXmlVisits(parseOrderedXml(entry.bytes, inspected.limits));
  const roots = visits.filter((visit) => visit.depth === 0);
  if (
    roots.length !== 1 ||
    roots[0]!.namespaceUri !== profile.rootNamespace ||
    roots[0]!.localName !== profile.rootLocalName
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_NAMESPACE_OR_ROOT_INVALID',
    );
  }
  for (const visit of visits) {
    assertAuxiliaryElementAndAttributes(visit, profile);
    if (
      (visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        BLOCKED_WORD_ELEMENTS.has(visit.localName)) ||
      (visit.namespaceUri === MARKUP_COMPATIBILITY_NAMESPACE &&
        visit.localName === 'AlternateContent')
    ) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_DYNAMIC_OR_REVISION_CONTENT',
      );
    }
  }
}

function assertAuxiliaryElementAndAttributes(
  visit: ExpandedXmlVisit,
  profile: AuxiliaryXmlProfile,
): void {
  const elementName = expandedNameKey(visit.namespaceUri, visit.localName);
  const allowedAttributes = profile.elements.get(elementName);
  if (!allowedAttributes) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_ELEMENT_OR_NAMESPACE_UNSUPPORTED',
    );
  }

  if (visit.parent) {
    if (
      !profile.edges.has(
        edgeKey(
          visit.parent.namespaceUri ?? '',
          visit.parent.localName,
          visit.namespaceUri ?? '',
          visit.localName,
        ),
      )
    ) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_ELEMENT_PLACEMENT_UNSUPPORTED',
      );
    }
  }

  const seenAttributes = new Set<string>();
  for (const attribute of visit.attributes) {
    const attributeName = expandedNameKey(
      attribute.namespaceUri,
      attribute.localName,
    );
    if (
      seenAttributes.has(attributeName) ||
      !allowedAttributes.has(attributeName)
    ) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_ATTRIBUTE_OR_NAMESPACE_UNSUPPORTED',
      );
    }
    seenAttributes.add(attributeName);
    if (
      attribute.namespaceUri === MARKUP_COMPATIBILITY_NAMESPACE &&
      attribute.localName === 'Ignorable'
    ) {
      assertIgnorableNamespaces(visit, attribute.value);
    }
  }

  for (const child of childrenOf(visit.node)) {
    if (tagOf(child) !== '#text') continue;
    const text = decodeXmlScalar(String(child['#text'] ?? ''));
    if (
      text.trim().length > 0 &&
      !(
        visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
        visit.localName === 't'
      )
    ) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_TEXT_PLACEMENT_UNSUPPORTED',
      );
    }
  }
}

function assertIgnorableNamespaces(
  visit: ExpandedXmlVisit,
  ignorableValue: string,
): void {
  const declarations = namespaceDeclarations(visit);
  const prefixes = ignorableValue.trim().split(/\s+/).filter(Boolean);
  if (
    prefixes.length === 0 ||
    new Set(prefixes).size !== prefixes.length ||
    prefixes.some((prefix) => {
      const namespaceUri = declarations.get(prefix);
      return (
        namespaceUri === undefined ||
        !SAFE_IGNORABLE_EXTENSION_NAMESPACES.has(namespaceUri)
      );
    })
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_IGNORABLE_NAMESPACE_UNSUPPORTED',
    );
  }
}

function namespaceDeclarations(
  visit: ExpandedXmlVisit,
): ReadonlyMap<string, string> {
  const declarations = new Map<string, string>();
  const lineage: ExpandedXmlVisit[] = [];
  for (let current: ExpandedXmlVisit | null = visit; current; current = current.parent) {
    lineage.push(current);
  }
  for (const current of lineage.reverse()) {
    for (const [rawName, rawValue] of Object.entries(current.node[':@'] ?? {})) {
      const name = rawName.startsWith('@_') ? rawName.slice(2) : rawName;
      if (name === 'xmlns') {
        declarations.set('', decodeXmlScalar(String(rawValue)));
      } else if (name.startsWith('xmlns:')) {
        declarations.set(
          name.slice('xmlns:'.length),
          decodeXmlScalar(String(rawValue)),
        );
      }
    }
  }
  return declarations;
}

function assertAuxiliaryRelationshipGraph(
  inspected: InspectedDocxPackage,
  glossaryNames: ReadonlySet<string>,
): void {
  const glossaryDocument = 'word/glossary/document.xml';
  const rootIncoming = inspected.relationships.filter(
    (relationship) => relationship.targetPartName === glossaryDocument,
  );
  if (
    rootIncoming.length !== 1 ||
    rootIncoming[0]!.sourcePartName !== inspected.mainPartName ||
    rootIncoming[0]!.type !== GLOSSARY_DOCUMENT_RELATIONSHIP
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_RELATIONSHIP_GRAPH_INVALID',
    );
  }

  const outgoing = inspected.relationships.filter(
    (relationship) => relationship.sourcePartName === glossaryDocument,
  );
  const hasRelationshipPart = glossaryNames.has(RELATIONSHIP_PART);
  if ((outgoing.length > 0) !== hasRelationshipPart) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_RELATIONSHIP_GRAPH_INVALID',
    );
  }
  for (const [partName, relationshipType] of CHILD_RELATIONSHIPS) {
    const incoming = inspected.relationships.filter(
      (relationship) => relationship.targetPartName === partName,
    );
    if (glossaryNames.has(partName)) {
      if (
        incoming.length !== 1 ||
        incoming[0]!.sourcePartName !== glossaryDocument ||
        incoming[0]!.type !== relationshipType
      ) {
        throw new TemplateTwinAuxiliaryPartUnsupportedError(
          'TT_AUXILIARY_RELATIONSHIP_GRAPH_INVALID',
        );
      }
    } else if (incoming.length > 0) {
      throw new TemplateTwinAuxiliaryPartUnsupportedError(
        'TT_AUXILIARY_RELATIONSHIP_GRAPH_INVALID',
      );
    }
  }
  if (
    outgoing.some(
      (relationship) =>
        CHILD_RELATIONSHIPS.get(relationship.targetPartName) !==
        relationship.type,
    ) ||
    inspected.relationships.some(
      (relationship) =>
        relationship.sourcePartName.startsWith('word/glossary/') &&
        relationship.sourcePartName !== glossaryDocument,
    )
  ) {
    throw new TemplateTwinAuxiliaryPartUnsupportedError(
      'TT_AUXILIARY_RELATIONSHIP_GRAPH_INVALID',
    );
  }
}
