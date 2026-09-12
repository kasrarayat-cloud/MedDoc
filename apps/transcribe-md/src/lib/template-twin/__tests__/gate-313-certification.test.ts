// ============================================================================
// RULING #313 · CERTIFICATION — re-verification holds (A13), and a list item
// printed twice costs the certificate (never the document).
// ----------------------------------------------------------------------------
// Driven THROUGH `certifyAndActivateTemplateTwin`, the gate-165 way, so the
// wiring is what is proved: an arm over a helper would stay green while the
// blocker line was deleted.
//
// WHAT WOULD MAKE THIS FAIL: delete the `listItemRepeated` blocker -> the
// repeated-shape arm certifies; have the validator's group checks depend on
// anything not in the manifest -> A13's re-verification stops reproducing.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
vi.mock('../twin-audit', () => ({ logTwinAudit: vi.fn(async () => undefined) }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { canonicalSha256 } from '../canonical';
import { prepareTemplateTwinFill } from '../fill-engine';
import {
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import { createOutputArtifactKey } from '../storage/keys';
import { renderTemplateDocx } from '../../note-template-docx/renderer';
import { validateTemplateTwin } from '../validation';
import {
  allIds,
  bullets,
  compiledForm,
  ctl,
  fact,
  heading,
  mappingsFor,
  membersByAlias,
  para,
  PMH,
  resolveAll,
} from './helpers-313';

const ACTOR = { userId: 'doctor-313', userEmail: 'synthetic.doctor@example.test', practiceId: 'practice-313' };
const NOTE_TEMPLATE_ID = 'note-template-313';
const COMPILED_VERSION_ID = 'compiled-version-313';
const CHECKED_AT = '2026-09-10T00:00:00.000Z';

const SINGLES: ReadonlyArray<[alias: string, tag: string, concept: string, value: string]> = [
  ['Chief complaint', 'cc', 'chief_complaint', 'Heartburn for two months'],
  ['Onset', 'onset', 'hpi.onset', 'Two months ago'],
  ['Location', 'location', 'hpi.location', 'Epigastric'],
  ['Quality', 'quality', 'hpi.quality', 'Burning'],
  ['Timing', 'timing', 'hpi.timing', 'After meals'],
  ['General', 'exam_general', 'exam.general', 'Alert, no acute distress'],
  ['Abdomen', 'exam_abdomen', 'exam.abdomen', 'Soft, non-tender'],
  ['Neck', 'exam_neck', 'exam.neck', 'Supple'],
  ['Lungs', 'exam_lungs', 'exam.lungs', 'Clear bilaterally'],
  ['Occupation', 'occupation', 'social_history.occupation', 'Teacher'],
];

const BODY = [
  heading('Synthetic consult — fictional example data'),
  ...SINGLES.map(([alias, tag], index) => para(ctl(alias, tag, 10 + index, '____'))),
  heading('Past Medical History'),
  ...bullets(PMH, 'pmh', 3, 100),
];

const FACTS = [
  ...SINGLES.map(([, , concept, value], index) => fact(`c-${index}`, concept, value)),
  fact('c-pmh-1', 'past_medical_history', 'Hypertension'),
  fact('c-pmh-2', 'past_medical_history', 'Type 2 diabetes mellitus'),
];

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

interface Stored {
  ir: TemplateDocIR;
  mappings: SemanticMapping[];
  manifest: ReturnType<typeof TemplateTwinFillManifestSchema.parse>;
  outputObjectKey: string;
  row: Record<string, unknown>;
  mappingsSha256: string;
}

/** Assemble the persisted row from a manifest built EXACTLY as the product
 *  builds one: the real validator, the real counts, the real renderer. */
async function storedProof(
  source: Buffer,
  ir: TemplateDocIR,
  mappings: SemanticMapping[],
  resolutions: FieldResolution[],
): Promise<Stored> {
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts: FACTS,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    allowUncertifiedForSyntheticTest: true,
    now: CHECKED_AT,
  });
  expect(validation.valid, JSON.stringify(validation.issues)).toBe(true);
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
    facts: FACTS,
    fields: resolutions,
    validation,
    counts: templateTwinCounts(resolutions, ir.fields),
  });
  const outputObjectKey = createOutputArtifactKey({
    practiceId: ACTOR.practiceId,
    visitId: 'synthetic-certification-visit',
    manifestSha256: canonicalSha256(manifest),
    outputSha256: rendered.outputSha256,
    idFactory: () => 'synthetic-output-artifact',
  });
  const mappingsSha256 = templateTwinMappingsSha256(mappings);
  const byId = new Map(mappings.map((m) => [m.fieldId, m]));
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
        lineageId: 'lineage-313',
        sha256: ir.source.sha256,
        sizeBytes: ir.source.sizeBytes,
        mimeType: ir.source.mimeType,
      },
      fields: ir.fields.map((field, index) => ({
        id: `field-def-${index}`,
        fieldId: field.fieldId,
        detectionStatus: 'CERTIFIED',
        mapping: { id: `mapping-${index}`, ...toMappingRow(byId.get(field.fieldId)!) },
      })),
    },
  };
  return { ir, mappings, manifest, outputObjectKey, row, mappingsSha256 };
}

async function certify(stored: Stored) {
  dbState.row = structuredClone(stored.row);
  const { certifyAndActivateTemplateTwin } = await import('../certification-lifecycle');
  return certifyAndActivateTemplateTwin({
    noteTemplateId: NOTE_TEMPLATE_ID,
    actor: ACTOR,
    expectedMappingsSha256: stored.mappingsSha256,
  }).then(
    () => null,
    (caught: unknown) => caught as { code?: string; blockers?: readonly string[] },
  );
}

let form: { source: Buffer; ir: TemplateDocIR; mappings: SemanticMapping[] };

beforeEach(async () => {
  const { source, ir } = await compiledForm(BODY);
  const concepts = Object.fromEntries(SINGLES.map(([alias, , concept]) => [alias, concept]));
  form = { source, ir, mappings: mappingsFor(ir, { ...concepts, [PMH]: 'past_medical_history' }) };
});

describe('#313 — the distributed synthetic proof certifies, and re-verifies (A13)', () => {
  it('prepareTemplateTwinFill distributes the synthetic PMH, and the stored manifest re-verifies', async () => {
    const prepared = await prepareTemplateTwinFill({
      compiledVersionId: COMPILED_VERSION_ID,
      noteTemplateId: NOTE_TEMPLATE_ID,
      noteTemplateVersion: 1,
      ir: form.ir,
      mappings: form.mappings,
      facts: FACTS,
      source: form.source,
      resolverModelVersion: null,
      validationNow: CHECKED_AT,
      allowUncertifiedForSyntheticTest: true,
    });
    const members = membersByAlias(form.ir, PMH);
    expect(members.map((m) => prepared.manifest.fields.find((f) => f.fieldId === m.fieldId)!.value)).toEqual([
      'Hypertension',
      'Type 2 diabetes mellitus',
      null,
    ]);
    const stored = await storedProof(form.source, form.ir, form.mappings, prepared.manifest.fields);
    // The manifest the fill produced and the one the proof stores are the same.
    expect(canonicalSha256(stored.manifest)).toBe(prepared.manifestSha256);
    const { isVerifiedSyntheticManifest } = await import('../certification-lifecycle');
    const verify = (manifest: unknown) =>
      isVerifiedSyntheticManifest({
        manifest,
        outputObjectKey: stored.outputObjectKey,
        compiledVersionId: COMPILED_VERSION_ID,
        noteTemplateId: NOTE_TEMPLATE_ID,
        noteTemplateVersion: 1,
        ir: form.ir,
        mappings: form.mappings,
      });
    expect(verify(stored.manifest)).toBe(true);
    // twin: move item 1 onto bullet 2 as well WITHOUT re-validating — the
    // stored validation no longer reproduces, so the proof is refused.
    const tampered = structuredClone(stored.manifest);
    const b2 = tampered.fields.find((f) => f.fieldId === members[1]!.fieldId)!;
    const b1 = tampered.fields.find((f) => f.fieldId === members[0]!.fieldId)!;
    Object.assign(b2, { value: b1.value, sourceFactIds: [...b1.sourceFactIds], evidenceAnchorIds: [...b1.evidenceAnchorIds] });
    expect(verify(tampered)).toBe(false);

    expect(await certify(stored)).toBeNull();
  });
});

describe('#313 — a list item printed twice costs the CERTIFICATE', () => {
  it('today\'s shape (every bullet the whole list) is valid at visit time and REFUSED at certification', async () => {
    const repeated = resolveAll(form.ir, form.mappings, FACTS); // no distribution
    const members = membersByAlias(form.ir, PMH);
    expect(new Set(members.map((m) => repeated.find((r) => r.fieldId === m.fieldId)!.value))).toEqual(
      new Set(['Hypertension; Type 2 diabetes mellitus']),
    );
    const stored = await storedProof(form.source, form.ir, form.mappings, repeated);
    expect(stored.manifest.validation.issues.map((i) => `${i.code}:${i.severity}`)).toContain('LIST_ITEM_REPEATED:warning');
    const error = await certify(stored);
    expect(error, 'a repeated list item certified').not.toBeNull();
    expect(error!.code).toBe('CERTIFICATION_BLOCKED');
    // ⚠️ MATCHED BY NAME, AND IT IS THE ONLY BLOCKER — the arm distinguishes
    // this invariant from a fixture that simply broke.
    expect(error!.blockers).toEqual([expect.stringMatching(/^listItemRepeated=false/)]);
  });

  it('TWIN: the same fixture distributed certifies (the only difference is the repeat)', async () => {
    const resolved = resolveAll(form.ir, form.mappings, FACTS);
    const { distributeListItems } = await import('../list-distribution');
    const distributed = distributeListItems({ ir: form.ir, mappings: form.mappings, facts: FACTS, resolutions: resolved });
    const stored = await storedProof(form.source, form.ir, form.mappings, distributed);
    expect(await certify(stored)).toBeNull();
    expect(allIds(form.ir).length).toBe(form.ir.fields.length);
  });
});

describe('#319 — repeated slots whose mappings DIFFER are refused at certification', () => {
  // ⚠️ AN ADVERSARIAL PASS FOUND THIS FALSE-GREEN. Three slots that share a
  // bullet-group identity but carry different mappings do NOT distribute — each
  // accumulates the whole joined list — yet the round-trip cannot see it (no group
  // forms, so no LIST_ITEM_REPEATED, and fill coverage is blind to distribution).
  // The certificate would ship a form that prints the whole list in every slot.
  it('a non-distributing repeated-slot form is BLOCKED at certification', async () => {
    const members = membersByAlias(form.ir, PMH);
    const perturbedId = members[1]!.fieldId;
    // Break bullet-group rule G7 on ONE slot — a different approvedSynonyms is a
    // compared key. The three no longer group; each PMH slot accumulates the whole
    // list (no fact matches the extra synonym, so the RESOLUTION is unchanged —
    // only the mapping identity differs, which is exactly the invisible case).
    const perturbed = form.mappings.map((mapping) =>
      mapping.fieldId === perturbedId
        ? ({ ...mapping, approvedSynonyms: ['past_surgical_history'] } as SemanticMapping)
        : mapping,
    );
    const resolved = resolveAll(form.ir, perturbed, FACTS); // no distribution
    const stored = await storedProof(form.source, form.ir, perturbed, resolved);
    const error = await certify(stored);
    expect(error, 'a non-distributing repeated-slot form certified').not.toBeNull();
    expect(error!.code).toBe('CERTIFICATION_BLOCKED');
    expect(
      error!.blockers?.some((blocker) => /^bulletGroupMappingsDiffer=false/.test(blocker)),
      `blockers were: ${JSON.stringify(error!.blockers)}`,
    ).toBe(true);
  });
});
