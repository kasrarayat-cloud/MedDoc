// ============================================================================
// Test helpers for ruling #313 — NOT a test file (no `.test.`), so vitest never
// collects it on its own.
//
// ⚠️ EVERY FIXTURE IS BUILT IN MEMORY FROM XML STRINGS. Nothing here writes a
// `.docx` to disk and no `.docx` is committed; the zip is produced by
// `buildSyntheticDocx`, the suite's existing writer.
//
// ⚠️ THIS MODULE MUST NOT IMPORT `fill-engine` — that module pulls the audit
// writer and next-auth into the graph, so each test file that needs the real
// `prepareTemplateTwinFill` mocks those edges itself.
// ============================================================================
import JSZip from 'jszip';

import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';
import { compileTemplateDocx } from '../../note-template-docx/compiler';
import { canonicalSha256 } from '../canonical';
import { expectedDataTypeForFieldKind } from '../field-kind-data-type';
import {
  EncounterFactSchema,
  SemanticMappingSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from '../ir';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';

export const NOW_313 = '2026-09-10T00:00:00.000Z';

const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';

export const text = (value: string): string =>
  `<w:r><w:t xml:space="preserve">${value}</w:t></w:r>`;
export const para = (...inner: string[]): string => `<w:p>${inner.join('')}</w:p>`;
export const heading = (value: string): string => para(text(value));

/** A plain-text content control, the same byte shape the consult-form
 *  generator emits (alias, tag, id, `w:text`, one run of scaffold). */
export function ctl(alias: string | null, tag: string | null, id: number, inner = '- ____'): string {
  return (
    `<w:sdt><w:sdtPr>` +
    (alias !== null ? `<w:alias w:val="${alias}"/>` : '') +
    (tag !== null ? `<w:tag w:val="${tag}"/>` : '') +
    `<w:id w:val="${id}"/><w:text/></w:sdtPr><w:sdtContent>${text(inner)}</w:sdtContent></w:sdt>`
  );
}

/** N bullet paragraphs, each ONLY a control whose scaffold is "- ____". */
export function bullets(
  alias: string,
  tag: string | null,
  count: number,
  idBase: number,
  scaffold = '- ____',
): string[] {
  return Array.from({ length: count }, (_, index) => para(ctl(alias, tag, idBase + index, scaffold)));
}

export function documentXml(body: readonly string[]): string {
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="${W}" xmlns:r="${R}"><w:body>${body.join('')}` +
    `<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/>` +
    `<w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>`
  );
}

export function headerXml(inner: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?><w:hdr xmlns:w="${W}">${inner}</w:hdr>`;
}

/** Build the package in memory and compile it with THE compiler. */
export async function compiledForm(
  body: readonly string[],
  options: { header?: string } = {},
): Promise<{ source: Buffer; ir: TemplateDocIR }> {
  const source = await buildSyntheticDocx({
    documentXml: documentXml(body),
    ...(options.header ? { extraEntries: { 'word/header1.xml': options.header } } : {}),
  });
  return { source, ir: compileTemplateDocx(new Uint8Array(source)) };
}

export function listMapping(
  field: TemplateField,
  concept: string,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  return SemanticMappingSchema.parse({
    sourceType: 'extraction',
    clinicalConcept: concept,
    expectedDataType: expectedDataTypeForFieldKind(field.kind),
    polarityBehavior: 'affirmative_only',
    temporality: null,
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
    fieldId: field.fieldId,
  });
}

/** A per-visit human field: always a designed blank, never a value. */
export function manualMapping(field: TemplateField): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: field.fieldId,
    sourceType: 'manual',
    clinicalConcept: null,
    expectedDataType: expectedDataTypeForFieldKind(field.kind),
    polarityBehavior: 'not_applicable',
    temporality: null,
    laterality: null,
    unitPolicy: null,
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  });
}

/** Every aliased field in `conceptByAlias` gets a list mapping; everything
 *  else (including the synthetic header's control) is `manual`. */
export function mappingsFor(
  ir: Pick<TemplateDocIR, 'fields'>,
  conceptByAlias: Readonly<Record<string, string>>,
  overrides: (field: TemplateField, indexInAlias: number) => Partial<SemanticMapping> = () => ({}),
): SemanticMapping[] {
  const seen = new Map<string, number>();
  return ir.fields.map((field) => {
    const alias = field.rendererBinding.alias;
    const concept = alias !== null ? conceptByAlias[alias] : undefined;
    if (concept === undefined) return manualMapping(field);
    const index = seen.get(alias!) ?? 0;
    seen.set(alias!, index + 1);
    return listMapping(field, concept, overrides(field, index));
  });
}

export function fact(
  seed: string,
  concept: string,
  value: string,
  overrides: Partial<EncounterFact> = {},
): EncounterFact {
  return EncounterFactSchema.parse({
    factId: `ttfact_${canonicalSha256(`fact:${seed}`).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: `Synthetic example dictation ${seed}.`,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
    ...overrides,
  });
}

export function membersByAlias(ir: Pick<TemplateDocIR, 'fields'>, alias: string): TemplateField[] {
  return ir.fields
    .filter((field) => field.rendererBinding.alias === alias)
    .sort((a, b) => a.displayOrder - b.displayOrder);
}

export function resolutionOf(
  resolutions: readonly FieldResolution[],
  field: Pick<TemplateField, 'fieldId'>,
): FieldResolution {
  const found = resolutions.filter((resolution) => resolution.fieldId === field.fieldId);
  if (found.length !== 1) throw new Error(`expected one resolution for ${field.fieldId}, found ${found.length}`);
  return found[0]!;
}

export function allIds(ir: Pick<TemplateDocIR, 'fields'>): string[] {
  return ir.fields.map((field) => field.fieldId);
}

/** THE resolver, over every field, with every field certified. */
export function resolveAll(
  ir: Pick<TemplateDocIR, 'fields'>,
  mappings: readonly SemanticMapping[],
  facts: readonly EncounterFact[],
): FieldResolution[] {
  return resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds: allIds(ir),
  });
}

/** THE validator, over every field, with every field certified. */
export function validateAll(
  ir: Pick<TemplateDocIR, 'fields' | 'tables' | 'unsupported'>,
  mappings: readonly SemanticMapping[],
  facts: readonly EncounterFact[],
  resolutions: readonly FieldResolution[],
) {
  return validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds: allIds(ir),
    now: NOW_313,
  });
}

/** The visible text of every content control in the body, in document order. */
export async function controlTexts(docx: Uint8Array): Promise<string[]> {
  const zip = await JSZip.loadAsync(docx);
  const xml = await zip.file('word/document.xml')!.async('string');
  return [...xml.matchAll(/<w:sdt\b[\s\S]*?<\/w:sdt>/g)].map((match) =>
    [...match[0].matchAll(/<w:t(?:\s[^>]*)?>([^<]*)<\/w:t>/g)].map((t) => t[1]).join(''),
  );
}

/** A pre-#313 stored IR: the same compile with the new property removed. */
export function withoutSoleParagraphControl(ir: TemplateDocIR): TemplateDocIR {
  return {
    ...ir,
    fields: ir.fields.map((field) => {
      const { soleParagraphControl: _sole, ...rest } = field;
      return rest as TemplateField;
    }),
  };
}

/** The Past Medical History ×3 form every arm starts from. */
export const PMH = 'Past Medical History';
export const PMH_BODY: readonly string[] = [heading('Past Medical History'), ...bullets(PMH, 'pmh', 3, 100)];
export const PMH_CONCEPTS = { [PMH]: 'past_medical_history' } as const;
