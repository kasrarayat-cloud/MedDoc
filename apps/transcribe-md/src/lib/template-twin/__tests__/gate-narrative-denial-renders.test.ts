// ============================================================================
// RULING #157 — A NARRATIVE FIELD PRINTS THE DENIAL'S PROSE.
// ----------------------------------------------------------------------------
// "No known drug allergies" is clinical CONTENT, not a checkbox-false. Denial is
// a POLARITY OF A FACT, and by the time a value reaches the renderer the
// resolver's evidence rails have already bound that sentence to a cited,
// dictated fact. So the refusal remains in exactly ONE place — a CHECKBOX whose
// value is not `false`, the only shape where printing would tick a box the
// encounter denied — and every other kind prints its denial.
//
// ⚠️ WHAT WAS BROKEN, AND IT WAS BOTH POLARITY BEHAVIOURS AT ONCE. Before this
// gate existed, a single denied sentence in a narrative section took the
// DOCTOR'S WHOLE DOCUMENT down, by two different routes:
//
//   explicit_denial_allowed -> value KEPT, status explicitly_denied
//                           -> renderer refused any non-checkbox   (arm C)
//   affirmative_only        -> value NULLED, status explicitly_denied
//                           -> renderer refused a populated status
//                              carrying no value                   (arm A)
//
// Both ended in FIELD_RESOLUTION_INVALID, and `validateTemplateTwin` returned
// `valid=true` with ZERO issues naming the field on the way there — so nothing
// upstream of the renderer could see it coming.
//
// ⚠️ WHAT THIS GATE DRIVES, because a replica of an assertion proves nothing
// about the assertion: the REAL compiler (`compileTemplateDocx`), the REAL
// resolver (`resolveTemplateFields`), the REAL validator
// (`validateTemplateTwin`) and the REAL, AWAITED `renderTemplateDocx`. The
// renderer recompiles its source and compares field hashes, so the IR here
// cannot be hand-built: every field below is a field the compiler actually
// emitted from a .docx.
//
// ⚠️ AN AWAITED RENDERER. `renderTemplateDocx` is ASYNC. A probe that calls it
// inside try/catch without `await` reports OK for EVERY input, including the
// ones that MUST fail, and that exact defect nearly produced a false "the fix
// is unnecessary" during the measurement pass. Every call below is awaited,
// through `await` or `expect(...).rejects`.
//
// ⚠️ ONE DENIAL AT A TIME, DELIBERATELY. A refusal kills the WHOLE package, so
// a fixture that denies every field at once makes every arm red whenever any
// single kind regresses — the arms stop discriminating and a half-landed fix
// reads exactly like a full revert. Each arm therefore denies only its OWN
// concept and leaves the rest affirmed, and arm (n) drives all of them at once
// to prove they still compose.
//
// ⚠️ WHAT THIS GATE DOES NOT CLAIM:
//   · it does not exercise the MODEL. The facts are the ideal extraction, one
//     per dictated concept, deliberately the best case.
//   · it does not claim the owner's real form certifies end to end. It asserts
//     the SHAPE of the owner's ord-21 Allergies field — narrative_text /
//     explicit_denial_allowed / concept `allergy` / criticality `allergy` —
//     compiled from a .docx, not a copy of that field.
//   · MULTI_SELECT'S RENDERER HALF IS STRUCTURALLY UNREACHABLE and is measured
//     rather than assumed. See arms (k) and (m).
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  compileTemplateDocx,
  inspectDocxPackage,
  renderTemplateDocx,
} from '@/lib/note-template-docx';
import {
  buildSyntheticDocx,
  syntheticOpc,
} from '../../note-template-docx/__tests__/synthetic-docx';
import {
  FieldResolutionSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../ir';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';

const REPO_ROOT = path.resolve(process.cwd(), '../..');
const WM_IOV_PATH = path.join(REPO_ROOT, 'WM IOV Template.docx');

/** The prose from the ruling itself. Asserted VERBATIM in the output package. */
const NKDA = 'No known drug allergies';
/** The sentence that actually took a production document down. */
const IMPRESSION = 'Stable chronic conditions with no acute change';

// ── the source document ──────────────────────────────────────────────────────
// Extends the shared synthetic package with the labels this gate needs. The
// compiler infers the KIND from the label, so these names are load-bearing:
// "Allergies" -> narrative_text + criticality `allergy` (the owner's ord 21),
// "Polyp count" -> number, "Lesion diameter" -> measurement.
//
// ⚠️ The shared package's DATA-BOUND control is dropped. It compiles
// `detectionStatus: 'unsupported'`, which the resolver answers with
// needs_clinician_input — BLOCKING for a clinically material field — and a
// blocked validation would make the renderer refuse with VALIDATION_REQUIRED
// before reaching the assertion under test. An overlapping guard must not
// launder the arm being proved.
const EXTRA_CONTROLS = `
<w:p><w:sdt><w:sdtPr><w:id w:val="301"/><w:alias w:val="Allergies"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter allergies</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="302"/><w:alias w:val="Impression"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter impression</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="303"/><w:alias w:val="Polyp count"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter count</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="304"/><w:alias w:val="Lesion diameter"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter diameter</w:t></w:r></w:sdtContent></w:sdt></w:p>
`;
const DATA_BOUND_CONTROL =
  '<w:p><w:sdt><w:sdtPr><w:id w:val="108"/><w:alias w:val="Data-bound synthetic value"/><w:text/><w:dataBinding w:xpath="/root/value" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:sdtPr><w:sdtContent><w:r><w:t>Unapproved bound value</w:t></w:r></w:sdtContent></w:sdt></w:p>';

function sourceDocumentXml(): string {
  const withoutDataBinding = syntheticOpc.documentXml.replace(
    DATA_BOUND_CONTROL,
    '',
  );
  // ASSERT THE EDIT APPLIED. A `.replace()` that matches nothing is a silent
  // no-op that returns the original string, and the unsupported control would
  // then reach the validator and refuse the render for the wrong reason.
  if (withoutDataBinding === syntheticOpc.documentXml) {
    throw new Error('synthetic package changed: data-bound control not removed');
  }
  return withoutDataBinding.replace('<w:sectPr>', `${EXTRA_CONTROLS}<w:sectPr>`);
}

// ── fixture builders ─────────────────────────────────────────────────────────

function factId(seed: number): string {
  return `ttfact_${seed.toString(16).padStart(24, '0')}`;
}

interface FactSpec {
  seed: number;
  concept: string;
  value: string;
}

function factAt(spec: FactSpec, polarity: EncounterFact['polarity']): EncounterFact {
  return {
    factId: factId(spec.seed),
    sourceType: 'encounter_evidence',
    concept: spec.concept,
    value: spec.value,
    polarity,
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`gate157-anchor-${spec.seed}`],
    evidenceQuote: `${spec.value} (synthetic dictation, gate 157)`,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  };
}

const CONCEPT = {
  allergy: 'allergy',
  assessment: 'assessment',
  side: 'exam.side',
  date: 'procedure.date',
  medication: 'medication',
  count: 'finding.polyp_count',
  measurement: 'measurement.lesion',
  rows: 'exam.abdomen',
} as const;

const FACT_SPECS: FactSpec[] = [
  { seed: 1, concept: CONCEPT.allergy, value: NKDA },
  { seed: 2, concept: CONCEPT.assessment, value: IMPRESSION },
  { seed: 3, concept: CONCEPT.side, value: 'R' },
  { seed: 4, concept: CONCEPT.date, value: '2026-02-03' },
  { seed: 5, concept: CONCEPT.medication, value: 'warfarin' },
  { seed: 6, concept: CONCEPT.count, value: '3' },
  { seed: 7, concept: CONCEPT.measurement, value: '4 mm' },
  { seed: 8, concept: CONCEPT.rows, value: 'No hepatomegaly.' },
  { seed: 9, concept: CONCEPT.rows, value: 'No splenomegaly.' },
];

const ALL_CONCEPTS = Object.values(CONCEPT);
const NOTHING_DENIED: readonly string[] = [];

/** Which compiled label carries which concept, and under which polarity
 *  behaviour. Every OTHER field gets a concept no fact names, so it resolves
 *  honestly `not_mentioned` and renders blank. */
const PLAN: Record<
  string,
  { concept: string; polarityBehavior: SemanticMapping['polarityBehavior'] }
> = {
  Allergies: { concept: CONCEPT.allergy, polarityBehavior: 'explicit_denial_allowed' },
  // ⚠️ THE OTHER HALF OF THE BREAKAGE. `affirmative_only` nulled the value and
  // died on arm A, so this row is not a duplicate of the one above — it proves
  // a DIFFERENT refusal.
  Impression: { concept: CONCEPT.assessment, polarityBehavior: 'affirmative_only' },
  'Exam side': { concept: CONCEPT.side, polarityBehavior: 'explicit_denial_allowed' },
  'Encounter date': { concept: CONCEPT.date, polarityBehavior: 'explicit_denial_allowed' },
  'Medication reviewed': { concept: CONCEPT.medication, polarityBehavior: 'explicit_denial_allowed' },
  'Polyp count': { concept: CONCEPT.count, polarityBehavior: 'explicit_denial_allowed' },
  'Lesion diameter': { concept: CONCEPT.measurement, polarityBehavior: 'explicit_denial_allowed' },
  'Repeat finding': { concept: CONCEPT.rows, polarityBehavior: 'explicit_denial_allowed' },
};

function mappingFor(field: TemplateField): SemanticMapping {
  const planned = PLAN[field.originalLabel];
  const expectedDataType = expectedDataTypeForFieldKind(field.kind);
  if (!expectedDataType) {
    throw new Error(`no expectedDataType for kind ${field.kind}`);
  }
  return {
    fieldId: field.fieldId,
    sourceType: 'extraction',
    clinicalConcept: planned?.concept ?? `gate157.unused.${field.fieldId}`,
    expectedDataType,
    polarityBehavior: planned?.polarityBehavior ?? 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: field.kind === 'measurement' ? 'optional' : 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  };
}

interface Driven {
  ir: TemplateDocIR;
  source: Buffer;
  facts: EncounterFact[];
  resolutions: FieldResolution[];
  validation: TemplateTwinValidationResult;
  byLabel(label: string): { field: TemplateField; resolution: FieldResolution };
  render(): Promise<string>;
}

let compiled: { source: Buffer; ir: TemplateDocIR } | null = null;

async function compiledSource(): Promise<{ source: Buffer; ir: TemplateDocIR }> {
  if (!compiled) {
    const source = await buildSyntheticDocx({ documentXml: sourceDocumentXml() });
    compiled = { source, ir: compileTemplateDocx(source) };
  }
  return compiled;
}

/** REAL compiler -> REAL resolver -> REAL validator. No replica anywhere.
 *  `deniedConcepts` names the concepts dictated in the NEGATIVE; everything
 *  else in the same encounter is affirmed, so an arm's red is about ITS kind. */
async function drive(deniedConcepts: readonly string[]): Promise<Driven> {
  const denied = new Set(deniedConcepts);
  // A misspelled concept here would silently make an arm test the AFFIRMED
  // path and pass for the wrong reason. Refuse it at the fixture.
  for (const concept of denied) {
    if (!ALL_CONCEPTS.includes(concept as (typeof ALL_CONCEPTS)[number])) {
      throw new Error(`gate 157: ${concept} is not a fixture concept`);
    }
  }
  const { source, ir } = await compiledSource();
  const mappings = ir.fields.map(mappingFor);
  const facts = FACT_SPECS.map((spec) =>
    factAt(spec, denied.has(spec.concept) ? 'denied' : 'affirmed'),
  );
  const certifiedFieldIds = ir.fields.map((field) => field.fieldId);
  const resolutions = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds,
  });
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds,
    now: '2026-01-01T00:00:00.000Z',
  });
  const driven: Driven = {
    ir,
    source,
    facts,
    resolutions,
    validation,
    byLabel(label) {
      const field = ir.fields.find((item) => item.originalLabel === label);
      if (!field) throw new Error(`no compiled field labelled ${label}`);
      const resolution = resolutions.find((item) => item.fieldId === field.fieldId);
      if (!resolution) throw new Error(`no resolution for ${label}`);
      return { field, resolution };
    },
    async render() {
      // EVERY ARM RE-ASSERTS THE VALIDATION IS CLEAN BEFORE RENDERING. Without
      // it a blocked validation would refuse with VALIDATION_REQUIRED and the
      // arm would read as "the renderer rejected the denial".
      expect(validation.valid).toBe(true);
      expect(validation.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
      const rendered = await renderTemplateDocx({
        source,
        ir,
        resolutions,
        validation,
      });
      expect(rendered.verification.verified).toBe(true);
      return documentXmlOf(rendered.document);
    },
  };
  return driven;
}

function documentXmlOf(rendered: Buffer): string {
  return inspectDocxPackage(rendered)
    .zip.entries.get('word/document.xml')!
    .bytes.toString('utf8');
}

/** The `w:sdt` element carrying this `w:id`, so a text assertion is about THAT
 *  FIELD rather than about the package. A document-wide `toContain` can be
 *  satisfied by a coincidental match in a neighbouring control, and "renders
 *  the prose VERBATIM" is a claim about one binding. */
function controlById(xml: string, id: string): string {
  const identity = xml.indexOf(`<w:id w:val="${id}"`);
  if (identity < 0) throw new Error(`no control with w:id ${id} in the output`);
  const start = xml.lastIndexOf('<w:sdt>', identity);
  if (start < 0) throw new Error(`control ${id} is malformed`);
  // ⚠️ BALANCED, NOT FIRST-CLOSE. A repeating section CONTAINS the controls it
  // repeats, so `indexOf('</w:sdt>')` returns the INNER control's close and
  // silently truncates the slice after row one — which reads as "the second row
  // did not render". Measured: it cut arm (g) in half.
  let depth = 0;
  let cursor = start;
  while (cursor < xml.length) {
    const open = xml.indexOf('<w:sdt>', cursor);
    const close = xml.indexOf('</w:sdt>', cursor);
    if (close < 0) break;
    if (open >= 0 && open < close) {
      depth += 1;
      cursor = open + '<w:sdt>'.length;
      continue;
    }
    depth -= 1;
    cursor = close + '</w:sdt>'.length;
    if (depth === 0) return xml.slice(start, cursor);
  }
  throw new Error(`control ${id} is unbalanced`);
}

/** Every field this gate reads, addressed by the `w:id` its own source XML
 *  carries. Named once so an arm cannot quietly assert against the wrong one. */
const CONTROL_ID = {
  'Exam side': '100',
  'Encounter date': '103',
  'Medication reviewed': '104',
  'Repeat finding': '106',
  Allergies: '301',
  Impression: '302',
  'Polyp count': '303',
  'Lesion diameter': '304',
} as const;

/** Swap ONE resolution and keep everything else exactly as the real pipeline
 *  produced it — including the real validation result, which stays `valid`. A
 *  refusal below therefore cannot come from VALIDATION_REQUIRED, and every
 *  refusing arm asserts its CODE rather than merely "it threw". */
function withResolution(
  driven: Driven,
  fieldId: string,
  patch: Partial<FieldResolution>,
): FieldResolution[] {
  return driven.resolutions.map((item) =>
    item.fieldId === fieldId
      ? FieldResolutionSchema.parse({ ...item, ...patch })
      : item,
  );
}

// ============================================================================

describe('RULING #157 — a narrative denial prints its prose, end to end', () => {
  it('(pre) the fixture reaches the renderer: the real validator is clean and every planned concept denies', async () => {
    const denied = await drive(ALL_CONCEPTS);
    // NON-VACUITY / ANTI-LAUNDERING. If this were not clean, every refusal arm
    // below would pass for the wrong reason.
    expect(denied.validation.valid).toBe(true);
    expect(
      denied.validation.issues.filter((issue) => issue.severity === 'blocking'),
    ).toEqual([]);

    // And the plan is not silently half-applied: every planned label exists in
    // the compiled IR and every one of them resolved to a DENIAL.
    const planned = Object.keys(PLAN);
    expect(planned).toHaveLength(8);
    for (const label of planned) {
      const { resolution } = denied.byLabel(label);
      expect([label, resolution.status]).toEqual([label, 'explicitly_denied']);
    }
  });

  it('(a) THE RULING — the owner\'s Allergies shape renders "No known drug allergies" VERBATIM', async () => {
    const denied = await drive([CONCEPT.allergy]);
    const { field, resolution } = denied.byLabel('Allergies');

    // The shape being claimed, asserted rather than described: this is the
    // owner's ord 21 — narrative_text, concept `allergy`, denial-approving,
    // clinically material.
    expect(field.kind).toBe('narrative_text');
    expect(field.criticality).toBe('allergy');
    expect(field.clinicallyMaterial).toBe(true);
    expect(mappingFor(field).polarityBehavior).toBe('explicit_denial_allowed');

    // The resolver keeps the PROSE under a denial status, and cites it.
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(NKDA);
    expect(resolution.reasonCode).toBe('explicit_denial_supported');
    expect(resolution.sourceFactIds).toEqual([factId(1)]);

    // VERBATIM, IN THIS FIELD'S OWN CONTROL — not "it did not throw", and not
    // "the string appears somewhere in the package".
    const xml = await denied.render();
    expect(controlById(xml, CONTROL_ID.Allergies)).toContain(`<w:t>${NKDA}</w:t>`);
  });

  it('(b) the OTHER broken behaviour: `affirmative_only` no longer nulls the value, and its prose renders too', async () => {
    const denied = await drive([CONCEPT.assessment]);
    const { field, resolution } = denied.byLabel('Impression');
    expect(mappingFor(field).polarityBehavior).toBe('affirmative_only');
    // The arm-A half: the value used to be NULL here.
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(IMPRESSION);

    const xml = await denied.render();
    expect(controlById(xml, CONTROL_ID.Impression)).toContain(
      `<w:t>${IMPRESSION}</w:t>`,
    );
  });

  it('(c) CHECKBOX — explicitly_denied + false still RENDERS, as the unchecked box', async () => {
    const denied = await drive([CONCEPT.medication]);
    const { field, resolution } = denied.byLabel('Medication reviewed');
    expect(field.kind).toBe('checkbox');
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(false);

    const box = controlById(await denied.render(), CONTROL_ID['Medication reviewed']);
    expect(box).toContain('w14:checked w14:val="0"');
    expect(box).toContain('☐');
  });

  it('(d) THE REFUSAL THAT MUST SURVIVE — a checkbox explicitly_denied + true still refuses the DOCUMENT', async () => {
    const denied = await drive([CONCEPT.medication]);
    const { field, resolution } = denied.byLabel('Medication reviewed');
    expect(field.kind).toBe('checkbox');

    // The real resolver cannot produce this pair (`convertValue` gives a denied
    // checkbox `false`), so it is constructed directly — which is correct,
    // because the assertion under test is the RENDERER'S, and the renderer's
    // job is to refuse a pair no matter who hands it over.
    await expect(
      renderTemplateDocx({
        source: denied.source,
        ir: denied.ir,
        resolutions: withResolution(denied, resolution.fieldId, { value: true }),
        validation: denied.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });

  it('(e) ARM A IS UNTOUCHED — explicitly_denied carrying NO value still refuses', async () => {
    const denied = await drive([CONCEPT.allergy]);
    const { resolution } = denied.byLabel('Allergies');
    await expect(
      renderTemplateDocx({
        source: denied.source,
        ir: denied.ir,
        resolutions: withResolution(denied, resolution.fieldId, {
          value: null,
          sourceFactIds: [],
          evidenceAnchorIds: [],
        }),
        validation: denied.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });

  it('(f) ARM B IS UNTOUCHED — a non-null value under a non-populated status still refuses', async () => {
    const denied = await drive([CONCEPT.allergy]);
    const { resolution } = denied.byLabel('Allergies');
    for (const status of [
      'ambiguous',
      'conflict',
      'needs_clinician_input',
      'not_mentioned',
    ] as const) {
      await expect(
        renderTemplateDocx({
          source: denied.source,
          ir: denied.ir,
          resolutions: withResolution(denied, resolution.fieldId, { status }),
          validation: denied.validation,
        }),
      ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
    }
  });

  it('(g) ROW PROTOTYPE — a repeating narrative denial expands its rows and prints every one', async () => {
    const denied = await drive([CONCEPT.rows]);
    const { field, resolution } = denied.byLabel('Repeat finding');
    // ⚠️ THE SITE THE EARLIER PASS FOUND INVISIBLE. `resolver/index.ts`'s
    // rowPrototype branch has ALWAYS carried a non-null array under
    // `explicitly_denied`, so the old arm C refused the whole document here for
    // EVERY field kind — and no gate looked.
    expect(field.rowPrototype).toBe(true);
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.reasonCode).toBe('repeating_rows_explicitly_denied');
    expect(Array.isArray(resolution.value)).toBe(true);
    expect(resolution.value).toHaveLength(2);

    const section = controlById(await denied.render(), CONTROL_ID['Repeat finding']);
    expect(section).toContain('<w:t>No hepatomegaly.</w:t>');
    expect(section).toContain('<w:t>No splenomegaly.</w:t>');
  });

  it('(h) SINGLE_SELECT — a denied dropdown now SELECTS its option (pinned residual, owner question)', async () => {
    const denied = await drive([CONCEPT.side]);
    const { field, resolution } = denied.byLabel('Exam side');
    expect(field.kind).toBe('single_select');
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe('R');
    expect(resolution.selectedOptionOrdinal).toBe(1);
    // ⚠️ NAMED RESIDUAL, PINNED RATHER THAN ABSENT — AND IT IS AN OWNER
    // QUESTION, NOT A BUG THIS GATE ENDORSES. On a dropdown the "prose" of a
    // denial IS the option, so a denied fact SELECTS "Right" where it
    // previously refused the document. That is the same false-assertion shape
    // the checkbox carve-out exists to prevent, one control type over. It is
    // unreachable in today's corpus — all 28 production single_selects carry
    // `sourceType: verified_note_selection` and divert before this path — and
    // it RE-ARMS the day any uploaded form maps a dropdown to `extraction`
    // under a denial-approving polarityBehavior. Ruling #157 names only the
    // checkbox; widening the carve-out is class (a) and is not taken here.
    expect(controlById(await denied.render(), CONTROL_ID['Exam side'])).toContain(
      '<w:t>Right</w:t>',
    );
  });

  it('(h2) NUMBER, DATE and MEASUREMENT — each denies independently and prints its own value', async () => {
    const count = await drive([CONCEPT.count]);
    expect(count.byLabel('Polyp count').field.kind).toBe('number');
    expect(count.byLabel('Polyp count').resolution.status).toBe('explicitly_denied');
    expect(count.byLabel('Polyp count').resolution.value).toBe(3);
    expect(controlById(await count.render(), CONTROL_ID['Polyp count'])).toContain(
      '<w:t>3</w:t>',
    );

    const date = await drive([CONCEPT.date]);
    expect(date.byLabel('Encounter date').field.kind).toBe('date');
    expect(date.byLabel('Encounter date').resolution.status).toBe('explicitly_denied');
    expect(date.byLabel('Encounter date').resolution.value).toBe('2026-02-03');
    expect(controlById(await date.render(), CONTROL_ID['Encounter date'])).toContain(
      'w:fullDate="2026-02-03T00:00:00Z"',
    );

    const size = await drive([CONCEPT.measurement]);
    expect(size.byLabel('Lesion diameter').field.kind).toBe('measurement');
    expect(size.byLabel('Lesion diameter').resolution.status).toBe('explicitly_denied');
    expect(size.byLabel('Lesion diameter').resolution.value).toBe('4 mm');
    expect(controlById(await size.render(), CONTROL_ID['Lesion diameter'])).toContain(
      '<w:t>4 mm</w:t>',
    );
  });

  it('(i) NON-VACUITY CONTROL — the SAME fixture at AFFIRMED polarity renders, which isolates the change to polarity', async () => {
    const affirmed = await drive(NOTHING_DENIED);
    const { resolution } = affirmed.byLabel('Allergies');
    expect(resolution.status).toBe('supported');
    expect(resolution.value).toBe(NKDA);

    const xml = await affirmed.render();
    // The identical prose, under the identical binding — so a red in arm (a)
    // is about the STATUS, never about the fixture, the prose or the package.
    expect(controlById(xml, CONTROL_ID.Allergies)).toContain(`<w:t>${NKDA}</w:t>`);
    const box = controlById(xml, CONTROL_ID['Medication reviewed']);
    expect(box).toContain('w14:checked w14:val="1"');
    expect(box).toContain('☒');
  });

  it('(j) NON-VACUITY CONTROL — the renderer still refuses what it always refused', async () => {
    // Driven at AFFIRMED polarity on purpose: this arm must be INVARIANT to
    // #157, so that a revert of the fix cannot make it red and mask what the
    // rest of the gate is saying.
    const affirmed = await drive(NOTHING_DENIED);
    const side = affirmed.byLabel('Exam side');
    // A display label where an exact option value is required. Unrelated to
    // #157, and it must still fail. If this ever passes, the gate has stopped
    // measuring the renderer at all.
    await expect(
      renderTemplateDocx({
        source: affirmed.source,
        ir: affirmed.ir,
        resolutions: withResolution(affirmed, side.resolution.fieldId, {
          value: 'Right',
        }),
        validation: affirmed.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_VALUE_INVALID' });

    // And a blocked validation still refuses BEFORE any of this — the guard
    // whose overlap the arms above are deliberately kept clear of.
    await expect(
      renderTemplateDocx({
        source: affirmed.source,
        ir: affirmed.ir,
        resolutions: affirmed.resolutions,
        validation: {
          ...affirmed.validation,
          valid: false,
          issues: [
            {
              fieldId: null,
              code: 'GATE157_SYNTHETIC_BLOCK',
              severity: 'blocking',
              message: 'Synthetic blocking result.',
            },
          ],
        },
      }),
    ).rejects.toMatchObject({ code: 'VALIDATION_REQUIRED' });
  });

  it('(k) MULTI_SELECT — the resolver carries the denial as its option array, never as null', async () => {
    // ⚠️ THE SECOND SITE THE EARLIER PASS FOUND INVISIBLE
    // (`resolver/index.ts`, the multi_select branch). It is driven through the
    // REAL resolver; its renderer half is measured as unreachable in arm (m).
    const optionField: TemplateField = {
      fieldId: `ttf_${'1'.repeat(24)}`,
      kind: 'multi_select',
      originalLabel: 'Reported symptoms',
      labelSource: 'alias',
      displayOrder: 0,
      detectionStatus: 'certified',
      allowedOptions: [
        { ordinal: 0, value: 'nausea', displayText: 'Nausea' },
        { ordinal: 1, value: 'vomiting', displayText: 'Vomiting' },
      ],
      rendererBinding: {
        partName: 'word/document.xml',
        bindingType: 'content_control',
        path: '/gate157/multi',
        ordinal: 0,
        sdtId: '901',
        tag: null,
        alias: 'Reported symptoms',
        legacyName: null,
        rowLaterality: 'unknown',
        tableIndex: null,
        rowIndex: null,
        cellIndex: null,
        repeatAncestorPath: null,
        sourceControlSha256: 'c'.repeat(64),
        originalContentSha256: 'd'.repeat(64),
      },
      required: false,
      unknownPolicy: 'blank',
      clinicallyMaterial: false,
      criticality: 'routine',
      tableId: null,
      rowPrototype: false,
    };
    const optionMapping: SemanticMapping = {
      ...mappingFor(optionField),
      clinicalConcept: 'ros.symptom',
      polarityBehavior: 'explicit_denial_allowed',
    };
    const denials = [
      factAt({ seed: 21, concept: 'ros.symptom', value: 'nausea' }, 'denied'),
      factAt({ seed: 22, concept: 'ros.symptom', value: 'vomiting' }, 'denied'),
    ];
    const [resolution] = resolveTemplateFields({
      fields: [optionField],
      mappings: [optionMapping],
      facts: denials,
      certifiedFieldIds: [optionField.fieldId],
    });
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.reasonCode).toBe('explicit_denial_exact_options');
    expect(resolution.value).toEqual(['nausea', 'vomiting']);

    // CONTROL: the affirmed twin of the same fixture, so a red above is about
    // polarity rather than about the option matching.
    const [affirmed] = resolveTemplateFields({
      fields: [optionField],
      mappings: [optionMapping],
      facts: denials.map((fact) => ({ ...fact, polarity: 'affirmed' as const })),
      certifiedFieldIds: [optionField.fieldId],
    });
    expect(affirmed.status).toBe('supported');
    expect(affirmed.value).toEqual(['nausea', 'vomiting']);
  });

  it('(m) CENSUS — multi_select is UNREACHABLE through the renderer, measured rather than assumed', async () => {
    // The renderer recompiles its source and compares field hashes, so a
    // hand-built field can never reach it. The compiler emits no `multi_select`
    // for any .docx, which is why arm (k) stops at the resolver. Stated as a
    // MEASUREMENT with its re-arming condition: the day `compileTemplateDocx`
    // emits a multi_select field, this arm reds and the renderer half of (k)
    // must be written.
    const { ir } = await compiledSource();
    const wmIov = compileTemplateDocx(new Uint8Array(readFileSync(WM_IOV_PATH)));
    const kinds = (fields: readonly TemplateField[]): Record<string, number> => {
      const out: Record<string, number> = {};
      for (const field of fields) out[field.kind] = (out[field.kind] ?? 0) + 1;
      return out;
    };
    const syntheticKinds = kinds(ir.fields);
    const realKinds = kinds(wmIov.fields);

    // POSITIVE CONTROL ON THE CENSUS ITSELF: it CAN see kinds, and it sees the
    // ones this gate depends on. A census that reported 0 for everything would
    // otherwise "prove" unreachability by being broken.
    expect(syntheticKinds.narrative_text).toBeGreaterThan(0);
    expect(syntheticKinds.single_select).toBeGreaterThan(0);
    expect(syntheticKinds.checkbox).toBeGreaterThan(0);
    expect(syntheticKinds.number).toBeGreaterThan(0);
    expect(syntheticKinds.date).toBeGreaterThan(0);
    expect(syntheticKinds.measurement).toBeGreaterThan(0);
    // ARITHMETIC THAT RECONCILES: the buckets add up to the field count.
    expect(Object.values(syntheticKinds).reduce((sum, n) => sum + n, 0)).toBe(
      ir.fields.length,
    );
    expect(Object.values(realKinds).reduce((sum, n) => sum + n, 0)).toBe(
      wmIov.fields.length,
    );

    expect(syntheticKinds.multi_select ?? 0).toBe(0);
    expect(realKinds.multi_select ?? 0).toBe(0);
    // The real customer form, for the record: 28 dropdowns + 52 narrative.
    expect(wmIov.fields).toHaveLength(80);
  });

  it('(n) COMPOSITION — every kind denied AT ONCE still renders one document, with each denial in its own field', async () => {
    const denied = await drive(ALL_CONCEPTS);
    const xml = await denied.render();
    expect(controlById(xml, CONTROL_ID.Allergies)).toContain(`<w:t>${NKDA}</w:t>`);
    expect(controlById(xml, CONTROL_ID.Impression)).toContain(`<w:t>${IMPRESSION}</w:t>`);
    expect(controlById(xml, CONTROL_ID['Exam side'])).toContain('<w:t>Right</w:t>');
    expect(controlById(xml, CONTROL_ID['Polyp count'])).toContain('<w:t>3</w:t>');
    expect(controlById(xml, CONTROL_ID['Lesion diameter'])).toContain('<w:t>4 mm</w:t>');
    expect(controlById(xml, CONTROL_ID['Encounter date'])).toContain(
      'w:fullDate="2026-02-03T00:00:00Z"',
    );
    expect(controlById(xml, CONTROL_ID['Medication reviewed'])).toContain(
      'w14:checked w14:val="0"',
    );
    const section = controlById(xml, CONTROL_ID['Repeat finding']);
    expect(section).toContain('<w:t>No hepatomegaly.</w:t>');
    expect(section).toContain('<w:t>No splenomegaly.</w:t>');
  });
});
