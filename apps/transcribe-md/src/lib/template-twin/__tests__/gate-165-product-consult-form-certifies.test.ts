// ============================================================================
// RULING #165 — THE PRODUCT, END TO END: A CONSULT FORM CERTIFIES ON `emptied`
// PROOFS ALONE.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS FILE EXISTS, STATED AS A MEASUREMENT RATHER THAN AS AN INTENTION.
//
// #164 changed WHAT CERTIFICATION COUNTS — `blankProofCount` became
// `blank ∪ emptied` — and every test it shipped asserted a PROOF'S LABEL:
// "the renderer emits `emptied`", "`countsAsBlankProof` returns true for it".
// Those are facts about a helper and about a string. They are not facts about
// the product.
//
// The consequence was measured, not imagined. An adversarial lens reverted the
// entire production wiring in `certification-lifecycle.ts` — putting the old
//
//     roundTripFields.filter((entry) => (entry as { kind?: string }).kind === 'blank')
//
// back in place of the `countsAsBlankProof` census — and **1678 tests still
// passed**. The counting rule that decides whether a doctor's form may be
// certified had NO test between it and `main`.
//
// ⚠️ THE DISTINCTION THIS FILE IS BUILT ON: a rule reachable only through its
// own helper is a rule whose arms prove the HELPER. This file drives
// `certifyAndActivateTemplateTwin` — the exported product function, the one the
// certify action and the auto-certify worker both call — and reads its verdict.
// The only way it can pass is if the shipped census actually counts `emptied`.
//
// THE VERDICT FLIP IT PINS, which is the whole of #165's product claim:
//
//   · a consult form whose ONLY blank evidence is `emptied` → CERTIFIES;
//   · the same form with that evidence removed from the census → BLOCKED, with
//     `blankVerification=false` named in the blockers.
//
// ⚠️ AND THE FIXTURE IS DELIBERATELY A FORM WITH **NO `blank` PROOF ANYWHERE**.
// That is what makes the arms non-vacuous: under #164's reverted predicate the
// census scores 0 and certification refuses. A fixture carrying even one
// unpatched field would certify under BOTH predicates and prove nothing — so
// arm 1 measures that property FIRST and fails loudly if it ever stops holding.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';
import { canonicalSha256 } from '../canonical';
import { countsAsBlankProof } from '../blank-proof-count';
import { MIN_CERTIFIED_FILLED_FIELDS } from '../certification-thresholds';
import {
  EncounterFactSchema,
  FieldResolutionSchema,
  SemanticMappingSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import { createOutputArtifactKey } from '../storage/keys';
import { validateTemplateTwin } from '../validation';

// ── THE DATABASE SEAM ───────────────────────────────────────────────────────
// `certifyAndActivateTemplateTwin` reaches persistence twice and only twice:
// `prisma.$transaction(cb)` -> `loadOwnedCompilation(tx, …)`, which is ONE
// `noteTemplate.findFirst`; and afterwards `readTemplateTwinWorkspace`, which
// is the SAME call on the singleton. One row therefore serves both, and the
// mock returns whatever `dbState.row` currently holds — which is what lets the
// BLOCK arm re-run the identical fixture with one field of the stored proof
// changed and nothing else.
const dbState = vi.hoisted(() => ({ row: null as unknown }));

vi.mock('@meddoc/db', () => {
  const client = {
    noteTemplate: {
      findFirst: vi.fn(async () => dbState.row),
      update: vi.fn(async () => ({})),
      updateMany: vi.fn(async () => ({ count: 0 })),
    },
    templateTwinCertification: { create: vi.fn(async () => ({})) },
    templateTwinCompiledVersion: { update: vi.fn(async () => ({})) },
    templateTwinFieldDefinition: { updateMany: vi.fn(async () => ({ count: 0 })) },
    $transaction: vi.fn(async (cb: (tx: unknown) => Promise<unknown>) => cb(client)),
  };
  return { default: client };
});

// ⚠️ MOCKED TO KEEP `next-auth` OUT OF THE MODULE GRAPH, NOT FOR CONVENIENCE.
// `twin-audit` -> `@/lib/audit` -> `@/lib/nextauth` + `next/headers`, which is
// the exact edge `certification-thresholds.ts` records as having broken this
// test environment outright ("Cannot find module .../next/server"). Certifying
// writes two audit rows; nothing in this gate is a claim about them.
vi.mock('../twin-audit', () => ({ logTwinAudit: vi.fn(async () => undefined) }));

const ACTOR = {
  userId: 'doctor-165',
  userEmail: 'synthetic.doctor@example.test',
  practiceId: 'practice-165',
};
const NOTE_TEMPLATE_ID = 'note-template-165';
const COMPILED_VERSION_ID = 'compiled-version-165';
const CHECKED_AT = '2026-01-01T00:00:00.000Z';

// ── THE FIXTURE: A CONSULT FORM, NOT A VENOUS GRID ──────────────────────────
// Twelve content controls in the body — seven `w:text` narrative sections and
// five `w:dropDownList` selections — plus the header control that
// `buildSyntheticDocx` always ships. NO table cells and NO legacy `w:fldChar`
// fields, deliberately: `table_cell` and `legacy_form_field` have no bounded
// container the writer clears, so an `emptied` proof from either does not count
// (`PROVEN_EMPTIABLE_BINDINGS`). A fixture containing them would leave the
// reader unable to say which binding bought the blank.
const NARRATIVE = (id: number, alias: string, placeholder: string): string =>
  `<w:p><w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/>` +
  `<w:text/></w:sdtPr><w:sdtContent><w:r><w:t>${placeholder}</w:t></w:r>` +
  `</w:sdtContent></w:sdt></w:p>`;

const SELECT = (
  id: number,
  alias: string,
  options: ReadonlyArray<string>,
): string =>
  `<w:p><w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/>` +
  `<w:dropDownList>` +
  options.map((o) => `<w:listItem w:displayText="${o}" w:value="${o}"/>`).join('') +
  `</w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r>` +
  `</w:sdtContent></w:sdt></w:p>`;

const CONSULT_FORM_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
  `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
  `<w:body>` +
  `<w:p><w:r><w:t>Synthetic consult form — fictional example data.</w:t></w:r></w:p>` +
  NARRATIVE(301, 'Chief complaint', 'Enter chief complaint') +
  NARRATIVE(302, 'History of present illness', 'Enter history') +
  NARRATIVE(303, 'Past medical history', 'Enter past medical history') +
  NARRATIVE(304, 'Assessment', 'Enter assessment') +
  NARRATIVE(305, 'Plan', 'Enter plan') +
  NARRATIVE(306, 'Physical exam', 'Enter exam') +
  NARRATIVE(307, 'Review of systems', 'Enter review of systems') +
  SELECT(308, 'Exam side', ['Left', 'Right', 'Bilateral']) +
  SELECT(309, 'Encounter category', ['Initial', 'Follow-up']) +
  SELECT(310, 'Severity', ['Mild', 'Moderate', 'Severe']) +
  SELECT(311, 'Disposition', ['Discharge', 'Admit', 'Refer']) +
  SELECT(312, 'Tobacco status', ['Never', 'Former', 'Current']) +
  `<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/>` +
  `<w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>` +
  `</w:body></w:document>`;

/**
 * What each compiled field is mapped to, and what the synthetic encounter says
 * about it. `null` means the encounter did not mention it — which is the whole
 * point of the fixture: those two fields are what the renderer CLEARS, and
 * their `emptied` proofs are the only blank evidence this certification has.
 *
 * ⚠️ KEYED BY THE COMPILER'S OWN LABEL, never by index. `ir.fields` order is
 * the compiler's business, and the header field arrives from a different part.
 */
const PLAN: ReadonlyArray<{
  label: string;
  concept: string;
  value: string | null;
}> = [
  { label: 'Chief complaint', concept: 'chief_complaint', value: 'Bilateral leg heaviness' },
  { label: 'History of present illness', concept: 'hpi.narrative', value: 'Six months of aching, worse standing' },
  { label: 'Past medical history', concept: 'past_medical_history', value: 'Hypertension' },
  { label: 'Assessment', concept: 'assessment', value: 'Chronic venous insufficiency' },
  { label: 'Plan', concept: 'plan', value: 'Compression stockings and review in three months' },
  { label: 'Physical exam', concept: 'exam.general', value: 'Visible varicosities, no ulceration' },
  // ⚠️ NULL ON PURPOSE — one of the two fields whose `emptied` proof is the
  // only thing standing between this fixture and `blankVerification=false`.
  { label: 'Review of systems', concept: 'ros.narrative', value: null },
  { label: 'Exam side', concept: 'exam.laterality', value: 'Bilateral' },
  { label: 'Encounter category', concept: 'encounter.category', value: 'Initial' },
  { label: 'Severity', concept: 'hpi.severity', value: 'Moderate' },
  { label: 'Disposition', concept: 'plan.disposition', value: 'Discharge' },
  // ⚠️ NULL ON PURPOSE — the second, and a SELECTION rather than a narrative,
  // because #164 excluded selections from `emptied` on a premise #165 measured
  // and refuted. If that exclusion ever returns, this fixture drops to one
  // blank proof and arm 4's arithmetic notices.
  { label: 'Tobacco status', concept: 'social_history.tobacco', value: null },
  { label: 'Practice display name', concept: 'practice.display_name', value: 'Synthetic Practice' },
];

/** `ttfact_[a-f0-9]{24}` — the schema's own shape, derived so it is stable. */
const factIdFor = (label: string): string =>
  `ttfact_${canonicalSha256(`fact:${label}`).slice(0, 24)}`;

interface Fixture {
  ir: TemplateDocIR;
  mappings: SemanticMapping[];
  resolutions: FieldResolution[];
  mappingsSha256: string;
  proofFields: Array<Record<string, unknown>>;
  row: Record<string, unknown>;
  bindingOf: (fieldId: string) => string | undefined;
}

/**
 * Compile -> map -> resolve -> render -> assemble the persisted row, using the
 * REAL compiler, validator and renderer at every step. Nothing here is a stand
 * in for the pipeline: the round-trip proof this stores is the one
 * `renderTemplateDocx` produced from these exact bytes.
 */
async function buildCertifiableConsultForm(): Promise<Fixture> {
  const source = await buildSyntheticDocx({ documentXml: CONSULT_FORM_XML });
  const { compileTemplateDocx } = await import('../../note-template-docx/compiler');
  const { renderTemplateDocx } = await import('../../note-template-docx/renderer');
  const ir = compileTemplateDocx(source);

  const planByLabel = new Map(PLAN.map((entry) => [entry.label, entry]));

  const mappings: SemanticMapping[] = [];
  const facts: EncounterFact[] = [];
  const resolutions: FieldResolution[] = [];

  for (const field of ir.fields) {
    const plan = planByLabel.get(field.originalLabel);
    if (!plan) {
      throw new Error(`fixture drift: compiler produced an unplanned field "${field.originalLabel}"`);
    }
    mappings.push(
      SemanticMappingSchema.parse({
        fieldId: field.fieldId,
        sourceType: 'extraction',
        clinicalConcept: plan.concept,
        // The gate requires COMPATIBILITY, so the type is read from the
        // compiled kind rather than asserted: narrative -> text, dropdown ->
        // single_select. Hard-coding either would be a fixture that agrees with
        // itself and not with the compiler.
        expectedDataType: field.kind === 'single_select' ? 'single_select' : 'text',
        polarityBehavior: 'affirmative_only',
        temporality: null,
        laterality: null,
        unitPolicy: null,
        approvedSynonyms: [],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        // ⚠️ NULL, AND IT IS NOT AN OMISSION. `updateTemplateTwinMappings`
        // REFUSES any non-null practice default outright ("a standing default
        // would put content the clinician never said into a signed note"), so a
        // fixture carrying one could never have been produced by the product.
        practiceDefault: null,
        status: 'certified',
      }),
    );

    if (plan.value === null) {
      resolutions.push(
        FieldResolutionSchema.parse({
          fieldId: field.fieldId,
          status: 'not_mentioned',
          value: null,
          sourceFactIds: [],
          evidenceAnchorIds: [],
          selectedOptionOrdinal: null,
          reasonCode: 'blank_when_unsaid',
          clinicianReviewed: false,
        }),
      );
      continue;
    }

    const factId = factIdFor(plan.label);
    const anchorId = `anchor-${field.displayOrder}`;
    facts.push(
      EncounterFactSchema.parse({
        factId,
        sourceType: 'encounter_evidence',
        concept: plan.concept,
        value: plan.value,
        polarity: 'affirmed',
        temporality: 'current',
        experiencer: 'patient',
        laterality: 'unknown',
        number: null,
        unit: null,
        speaker: null,
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [anchorId],
        evidenceQuote: `Synthetic example dictation: ${plan.value}.`,
        segment: null,
        quality: { asr: 'high', evidence: 'direct' },
      }),
    );
    const option = field.allowedOptions.find((o) => o.value === plan.value);
    resolutions.push(
      FieldResolutionSchema.parse({
        fieldId: field.fieldId,
        status: 'supported',
        value: plan.value,
        sourceFactIds: [factId],
        evidenceAnchorIds: [anchorId],
        selectedOptionOrdinal: option ? option.ordinal : null,
        reasonCode: 'supported_by_direct_evidence',
        clinicianReviewed: false,
      }),
    );
  }

  // ⚠️ THE REAL VALIDATOR, AND ITS OUTPUT IS WHAT THE MANIFEST STORES.
  // `isVerifiedSyntheticManifest` re-runs this exact call and compares the
  // canonical hashes, so a hand-written `{valid:true, issues:[]}` would be
  // rejected by the gate rather than accepted by it.
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    allowUncertifiedForSyntheticTest: true,
    now: CHECKED_AT,
  });

  const rendered = await renderTemplateDocx({ source, ir, resolutions, validation });

  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    compiledVersionId: COMPILED_VERSION_ID,
    noteTemplateId: NOTE_TEMPLATE_ID,
    noteTemplateVersion: 1,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: null,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    facts,
    fields: resolutions,
    validation,
    counts: templateTwinCounts(resolutions, ir.fields),
  });

  const mappingsSha256 = templateTwinMappingsSha256(mappings);
  // The gate parses this key and requires practice, kind and digest to agree
  // with the actor and the stored output — `createOutputArtifactKey` is the
  // product's own minter, so the shape cannot drift from the parser.
  const outputObjectKey = createOutputArtifactKey({
    practiceId: ACTOR.practiceId,
    visitId: 'synthetic-certification-visit',
    manifestSha256: canonicalSha256(manifest),
    outputSha256: rendered.outputSha256,
    idFactory: () => 'synthetic-output-artifact',
  });

  const proofFields = (rendered.verification.fields ?? []) as unknown as Array<
    Record<string, unknown>
  >;

  const mappingByFieldId = new Map(mappings.map((m) => [m.fieldId, m]));
  const row = {
    id: NOTE_TEMPLATE_ID,
    doctorId: ACTOR.userId,
    encounterType: 'consult',
    version: 1,
    name: 'Synthetic consult form',
    status: 'draft',
    templateTwinCompiledVersion: {
      id: COMPILED_VERSION_ID,
      compilerVersion: ir.compilerVersion,
      compiledAt: new Date(CHECKED_AT),
      compiledDocumentIr: ir,
      certificationStatus: 'NEEDS_CONFIRMATION',
      blockingUnsupportedCount: 0,
      latestSyntheticTestManifest: manifest,
      latestTestMappingsSha256: mappingsSha256,
      latestTestOutputObjectKey: outputObjectKey,
      latestTestOutputSha256: rendered.outputSha256,
      latestTestStaticContentSha256: ir.staticContentSha256,
      latestTestRoundTrip: rendered.verification,
      latestTestVerifiedAt: new Date(CHECKED_AT),
      certification: null,
      sourceArtifact: {
        practiceId: ACTOR.practiceId,
        lineageId: 'lineage-165',
        sha256: ir.source.sha256,
        sizeBytes: ir.source.sizeBytes,
        mimeType: ir.source.mimeType,
      },
      fields: ir.fields.map((field, index) => ({
        id: `field-def-${index}`,
        fieldId: field.fieldId,
        detectionStatus: 'CERTIFIED',
        mapping: { id: `mapping-${index}`, ...toMappingRow(mappingByFieldId.get(field.fieldId)!) },
      })),
    },
  };

  return {
    ir,
    mappings,
    resolutions,
    mappingsSha256,
    proofFields,
    row,
    bindingOf: (fieldId) =>
      ir.fields.find((f) => f.fieldId === fieldId)?.rendererBinding.bindingType,
  };
}

/** The persisted column shape `fromPersistedMapping` reads back. */
function toMappingRow(mapping: SemanticMapping): Record<string, unknown> {
  return {
    sourceType: mapping.sourceType,
    clinicalConcept: mapping.clinicalConcept,
    expectedDataType: mapping.expectedDataType,
    polarityBehavior: mapping.polarityBehavior,
    temporality: mapping.temporality,
    laterality: mapping.laterality,
    unitPolicy: mapping.unitPolicy,
    approvedSynonyms: mapping.approvedSynonyms,
    required: mapping.required,
    blankPolicy: mapping.blankPolicy,
    unknownPolicy: mapping.unknownPolicy,
    practiceDefault: mapping.practiceDefault,
    mappingStatus: 'CERTIFIED',
  };
}

/** Deep-clones the row so an arm's edit cannot leak into the next arm. */
function cloneRow(row: Record<string, unknown>): Record<string, unknown> {
  return structuredClone(row);
}

let fixture: Fixture;

beforeEach(async () => {
  fixture = await buildCertifiableConsultForm();
  dbState.row = cloneRow(fixture.row);
});

// ── ARM 1 — NON-VACUITY, AND IT RUNS FIRST BY DESIGN ────────────────────────
describe('#165 product — the fixture has NO `blank` proof, so `emptied` is load-bearing', () => {
  it('the rendered proof carries zero `blank` entries and at least one `emptied`', () => {
    const kinds = fixture.proofFields.map((p) => p.kind);
    // ⚠️ IF A GENUINE `blank` EVER APPEARS HERE, EVERY OTHER ARM IN THIS FILE
    // BECOMES VACUOUS: the certification would pass under #164's reverted
    // `kind === 'blank'` predicate too, and the mutation proof would go green
    // while the product regression it exists to catch shipped. That failure is
    // silent, so this assertion is loud and it is first.
    expect(kinds.filter((k) => k === 'blank')).toEqual([]);
    expect(kinds.filter((k) => k === 'emptied').length).toBeGreaterThanOrEqual(1);
    // and the whole field set is accounted for — no proof went missing.
    expect(fixture.proofFields.length).toBe(fixture.ir.fields.length);
  });

  it('the synthetic encounter fills enough fields to clear the fill-coverage floor', () => {
    const filled = fixture.resolutions.filter((r) => r.value !== null);
    expect(filled.length).toBeGreaterThanOrEqual(MIN_CERTIFIED_FILLED_FIELDS);
    // and it genuinely leaves something unmentioned, or there is nothing to clear.
    expect(fixture.resolutions.filter((r) => r.value === null).length).toBeGreaterThanOrEqual(2);
  });
});

// ── ARM 2 — THE PRODUCT PASSES ──────────────────────────────────────────────
describe('#165 product — a consult form certifies on `emptied` proofs alone', () => {
  it('certifyAndActivateTemplateTwin resolves', async () => {
    const { certifyAndActivateTemplateTwin } = await import('../certification-lifecycle');
    // ⚠️ NO try/catch AND NO `.rejects`. A thrown TemplateTwinLifecycleError
    // carries `blockers`, and vitest prints it — which is what makes a failure
    // here diagnosable rather than merely red.
    const workspace = await certifyAndActivateTemplateTwin({
      noteTemplateId: NOTE_TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: fixture.mappingsSha256,
    });
    expect(workspace.template.id).toBe(NOTE_TEMPLATE_ID);
    expect(workspace.fields.length).toBe(fixture.ir.fields.length);
  });
});

// ── ARM 3 — THE PRODUCT BLOCKS WHEN THE BLANK EVIDENCE IS TAKEN AWAY ────────
describe('#165 product — remove the `emptied` evidence and certification refuses', () => {
  it('blocks with blankVerification=false', async () => {
    const { certifyAndActivateTemplateTwin } = await import('../certification-lifecycle');
    const row = cloneRow(fixture.row) as never as {
      templateTwinCompiledVersion: { latestTestRoundTrip: { fields: Array<Record<string, unknown>> } };
    };
    // ⚠️ RELABELLED, NOT DELETED — AND THE REASON IS MEASURED, NOT STYLISTIC.
    // Deleting the two entries outright makes the proof carry 11 fields for a
    // 13-field IR, so `isVerifiedSyntheticProof` fails on its own arity check
    // and the run stops at `testReady=false` — a DIFFERENT gate, reached before
    // the blank census runs (the blank blocker is guarded by `testReady`). The
    // sibling arm below measures exactly that. To isolate ONE variable, the
    // entries stay structurally intact and lose only the property under test:
    // they stop being blank evidence.
    const proof = row.templateTwinCompiledVersion.latestTestRoundTrip;
    const relabelled = proof.fields.filter((f) => f.kind === 'emptied').length;
    expect(relabelled).toBeGreaterThanOrEqual(1);
    proof.fields = proof.fields.map((f) => (f.kind === 'emptied' ? { ...f, kind: 'filled' } : f));
    dbState.row = row;

    const error = await certifyAndActivateTemplateTwin({
      noteTemplateId: NOTE_TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: fixture.mappingsSha256,
    }).then(
      () => null,
      (caught: unknown) => caught as { code?: string; blockers?: readonly string[] },
    );

    expect(error, 'certification passed with no blank evidence at all').not.toBeNull();
    expect(error!.code).toBe('CERTIFICATION_BLOCKED');
    // ⚠️ THE BLOCKER IS MATCHED BY NAME. "It threw" is satisfied by any of the
    // gate's fifteen other refusals, several of which this edit could plausibly
    // trip — so asserting the throw alone would not distinguish the blank
    // invariant from a fixture that simply broke.
    expect(error!.blockers?.join(' | ')).toMatch(/blankVerification=false/);
  });

  it('deleting the entries instead stops one gate EARLIER — testReady, not blankVerification', async () => {
    // Recorded because it is the arm somebody will reach for first, and it
    // would look like a passing blank check while measuring arity.
    const { certifyAndActivateTemplateTwin } = await import('../certification-lifecycle');
    const row = cloneRow(fixture.row) as never as {
      templateTwinCompiledVersion: { latestTestRoundTrip: { fields: Array<Record<string, unknown>> } };
    };
    const proof = row.templateTwinCompiledVersion.latestTestRoundTrip;
    proof.fields = proof.fields.filter((f) => f.kind !== 'emptied');
    dbState.row = row;

    const error = await certifyAndActivateTemplateTwin({
      noteTemplateId: NOTE_TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: fixture.mappingsSha256,
    }).then(
      () => null,
      (caught: unknown) => caught as { code?: string; blockers?: readonly string[] },
    );

    expect(error).not.toBeNull();
    expect(error!.blockers?.join(' | ')).toMatch(/testReady=false.*proofReady/);
  });
});

// ── ARM 4 — THE ARITHMETIC, ON THE REAL PROOF ───────────────────────────────
describe('#165 product — the census the gate runs, driven directly on the same proof', () => {
  it('blank-only counts 0; blank ∪ emptied counts at least 2', () => {
    const blankOnly = fixture.proofFields.filter((p) => p.kind === 'blank').length;
    const union = fixture.proofFields.filter((p) =>
      countsAsBlankProof(p as never, fixture.bindingOf),
    ).length;

    // #164's reverted predicate scores this. Zero is why the PASS arm above is
    // a real measurement of the shipped census and not of the fixture.
    expect(blankOnly).toBe(0);
    // #165's shipped predicate scores this, on the same entries.
    expect(union).toBeGreaterThanOrEqual(2);
    // and the difference is entirely `emptied`, which is the counting rule.
    expect(union - blankOnly).toBe(
      fixture.proofFields.filter((p) => p.kind === 'emptied').length,
    );
  });
});

// ============================================================================
// THE PERSISTENCE BOUNDARY — a stored label is not a proof.
// ----------------------------------------------------------------------------
// ⚠️ FOUND BY THE ADVERSARIAL PASS, ON #165's OWN CHANGE, AND MEASURED.
// `isVerifiedSyntheticProof` is the gate that decides whether a stored proof is
// trustworthy. It compares exactly five per-field properties — `status`,
// `partName`, `bindingPath`, `valueSha256`, `occurrences` — and reads `kind`
// and `expectedSpanSha256` ZERO times. So the two fields that decide whether a
// clearing actually happened were the two nobody re-checked at the point of
// use, and a forged `emptied` with no expectation certified.
//
// That is #165's own label-versus-write defect one boundary down: the renderer
// now EARNS the label, and the read path was trusting it anyway.
// ============================================================================
describe('#165 product — an `emptied` label with no expectation is refused', () => {
  it('stripping `expectedSpanSha256` blocks with blankVerification=false', async () => {
    const { certifyAndActivateTemplateTwin } = await import('../certification-lifecycle');
    const row = cloneRow(fixture.row) as never as {
      templateTwinCompiledVersion: { latestTestRoundTrip: { fields: Array<Record<string, unknown>> } };
    };
    const proof = row.templateTwinCompiledVersion.latestTestRoundTrip;

    // ⚠️ STRUCTURALLY INTACT, ONE PROPERTY REMOVED — the same isolation the
    // relabelling arm above uses. The entries keep `kind: 'emptied'` and their
    // arity, so `isVerifiedSyntheticProof` still passes and the run reaches the
    // blank census. ONLY the expectation is gone.
    const forged = proof.fields.filter((f) => f.kind === 'emptied').length;
    expect(forged, 'fixture produced no emptied proof — this arm would be vacuous')
      .toBeGreaterThanOrEqual(1);
    proof.fields = proof.fields.map((f) => {
      if (f.kind !== 'emptied') return f;
      const { expectedSpanSha256: _dropped, ...rest } = f;
      return rest;
    });
    // NON-VACUITY: the property really is gone from every emptied entry.
    expect(
      proof.fields.filter((f) => f.kind === 'emptied' && 'expectedSpanSha256' in f).length,
    ).toBe(0);
    dbState.row = row;

    const error = await certifyAndActivateTemplateTwin({
      noteTemplateId: NOTE_TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: fixture.mappingsSha256,
    }).then(
      () => null,
      (caught: unknown) => caught as { code?: string; blockers?: readonly string[] },
    );

    expect(error, 'a forged `emptied` with no expectation still certified').not.toBeNull();
    expect(error!.code).toBe('CERTIFICATION_BLOCKED');
    expect(error!.blockers?.join(' | ')).toMatch(/blankVerification=false/);
  });

  it('a malformed expectation is refused too — well-formed means 64 hex', async () => {
    const { countsAsBlankProof } = await import('../blank-proof-count');
    const bindingOf = () => 'content_control';
    const base = { kind: 'emptied', fieldId: 'f1' };
    const good = 'a'.repeat(64);
    expect(countsAsBlankProof({ ...base, expectedSpanSha256: good }, bindingOf)).toBe(true);
    for (const bad of ['', 'A'.repeat(64), 'a'.repeat(63), 'a'.repeat(65), 'z'.repeat(64), 123]) {
      expect(
        countsAsBlankProof({ ...base, expectedSpanSha256: bad as never }, bindingOf),
        `accepted a malformed expectation: ${String(bad).slice(0, 12)}`,
      ).toBe(false);
    }
    // ⚠️ AND `blank` IS UNTOUCHED BY ALL OF THIS. It is unpatched and proven by
    // source-byte-identity; it carries no expectation and must never need one.
    expect(countsAsBlankProof({ kind: 'blank', fieldId: 'f2' }, bindingOf)).toBe(true);
  });
});
