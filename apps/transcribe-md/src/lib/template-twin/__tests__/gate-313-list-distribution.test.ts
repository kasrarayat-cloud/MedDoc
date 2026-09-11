// ============================================================================
// RULING #313 · ONE ITEM PER BULLET — the pass, its seam, and its second reader.
// ----------------------------------------------------------------------------
// WHAT WOULD MAKE THIS FAIL, stated before it was made to fail:
//  · move the pass AFTER the clinician overrides -> A1(c) (the doctor's default
//    on an unused bullet is declined, then blanked);
//  · put it inside the generated-note ternary -> A1(a) (no note, no pass);
//  · drop an item, repeat one, trim a one-fact bullet, split a joined string,
//    or strip the denials off bullet 1 -> A3/A4/A6;
//  · remove the legitimate-slot exemption -> the required-bullet arm (the pass
//    then cannot validate and leaves every bullet printing the whole list);
//  · remove any group check -> A9's hand-built manifests go green.
// Every refusal or warning arm has a twin that differs only in the discriminator.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

// `fill-engine` -> `twin-audit` -> `@/lib/audit` -> next-auth; and the prisma
// singleton. Neither is read by the pure paths under test.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { canonicalSha256 } from '../canonical';
import { applyClinicianOverrides, scaffoldDefaultOfferable } from '../clinician-override';
import { listItemCandidates } from '../fact-mapping-match';
import { prepareTemplateTwinFill } from '../fill-engine';
import {
  LIST_ITEM_SLOT_UNUSED_REASON,
  templateTwinCounts,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';
import { distributeListItems, planListDistribution } from '../list-distribution';
import { MIXED_POLARITY_REASON } from '../denial-contract';
import {
  approvedPracticeDefaultAnchorId,
  approvedPracticeDefaultFactId,
} from '../practice-default';
import {
  LIST_ITEM_DROPPED,
  LIST_ITEM_REPEATED,
  LIST_SLOT_UNUSED_ILLEGITIMATE,
} from '../validation';
import {
  allIds,
  bullets,
  compiledForm,
  controlTexts,
  fact,
  heading,
  mappingsFor,
  membersByAlias,
  NOW_313,
  PMH,
  PMH_BODY,
  PMH_CONCEPTS,
  resolutionOf,
  resolveAll,
  validateAll,
  withoutSoleParagraphControl,
} from './helpers-313';

const ITEMS = ['Hypertension', 'Type 2 diabetes mellitus', 'Asthma', 'Gout', 'Hypothyroidism', 'Migraine'];
const pmhFacts = (seed: string, values: readonly string[]): EncounterFact[] =>
  values.map((value, index) => fact(`${seed}-${index}`, 'past_medical_history', value));

async function pmhForm() {
  const { source, ir } = await compiledForm(PMH_BODY);
  return { source, ir, mappings: mappingsFor(ir, PMH_CONCEPTS), members: membersByAlias(ir, PMH) };
}

function prepare(input: {
  ir: TemplateDocIR;
  source?: Buffer;
  mappings: SemanticMapping[];
  facts: EncounterFact[];
  markerText?: string;
  generatedNote?: string;
  clinicianOverrides?: Parameters<typeof prepareTemplateTwinFill>[0]['clinicianOverrides'];
  allowUncertifiedForSyntheticTest?: boolean;
}) {
  return prepareTemplateTwinFill({
    compiledVersionId: 'cv-313',
    noteTemplateId: 'nt-313',
    noteTemplateVersion: 1,
    ir: input.ir,
    mappings: input.mappings,
    facts: input.facts,
    certifiedFieldIds: allIds(input.ir),
    source: input.source,
    resolverModelVersion: null,
    validationNow: NOW_313,
    markerText: input.markerText,
    generatedNote: input.generatedNote,
    clinicianOverrides: input.clinicianOverrides ?? [],
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
  });
}

const blocking = (issues: ReadonlyArray<{ severity: string; code: string }>) =>
  issues.filter((issue) => issue.severity === 'blocking').map((issue) => issue.code);

// ============================================================================
// A1 · THE SEAM — after the bridge, outside the ternary, before the doctor.
// ============================================================================
describe('#313 A1 — the seam', () => {
  it('(a) no generated note: bullets 1-2 carry one item each, bullet 3 is unused', async () => {
    const { source, ir, mappings, members } = await pmhForm();
    const prepared = await prepare({ ir, source, mappings, facts: pmhFacts('a1', ITEMS.slice(0, 2)) });
    const [b1, b2, b3] = members.map((m) => resolutionOf(prepared.manifest.fields, m));
    expect(b1).toMatchObject({ value: 'Hypertension', reasonCode: 'direct_evidence_supported' });
    expect(b2).toMatchObject({ value: 'Type 2 diabetes mellitus', reasonCode: 'direct_evidence_supported' });
    expect(b3).toMatchObject({ status: 'not_mentioned', value: null, reasonCode: LIST_ITEM_SLOT_UNUSED_REASON });
    expect(prepared.manifest.validation.valid).toBe(true);
    expect(prepared.render).not.toBeNull();
    const texts = await controlTexts(prepared.render!.document);
    expect(texts).toEqual(['Hypertension', 'Type 2 diabetes mellitus', '']);
  });

  it('(b) with a generated note and marker text: the SAME bullets', async () => {
    const { source, ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a1', ITEMS.slice(0, 2));
    const off = await prepare({ ir, source, mappings, facts });
    const on = await prepare({
      ir,
      source,
      mappings,
      facts,
      markerText: '',
      generatedNote: 'Past Medical History:\n- Hypertension\n- Type 2 diabetes mellitus\n',
    });
    for (const member of members) {
      expect(resolutionOf(on.manifest.fields, member)).toEqual(resolutionOf(off.manifest.fields, member));
    }
  });

  it('(c) a stored scaffold default on bullet 3 APPLIES — the doctor goes last', async () => {
    const { source, ir, mappings, members } = await pmhForm();
    const prepared = await prepare({
      ir,
      source,
      mappings,
      facts: pmhFacts('a1', ITEMS.slice(0, 2)),
      clinicianOverrides: [{ kind: 'scaffold_default', fieldId: members[2]!.fieldId, insertedText: 'No other history' }],
    });
    const [b1, b2, b3] = members.map((m) => resolutionOf(prepared.manifest.fields, m));
    expect(b1!.value).toBe('Hypertension');
    expect(b2!.value).toBe('Type 2 diabetes mellitus');
    expect(b3).toMatchObject({ value: 'No other history', reasonCode: 'clinician_scaffold_default' });
    expect(prepared.manifest.validation.issues.map((issue) => issue.code)).not.toContain('CLINICIAN_OVERRIDE_DECLINED');
    expect(prepared.manifest.validation.valid).toBe(true);
  });
});

// ============================================================================
// A2 · ORDER-INDEPENDENT, INPUT ORDER OUT, DETERMINISTIC.
// ============================================================================
describe('#313 A2 — order', () => {
  it('the same values whether the input is in resolver order or reversed; input order out', async () => {
    const { ir, mappings } = await pmhForm();
    const facts = pmhFacts('a2', ITEMS.slice(0, 3));
    const resolved = resolveAll(ir, mappings, facts);
    const reversed = [...resolved].reverse();
    const inIrOrder = ir.fields.map((field) => resolutionOf(resolved, field));
    const a = distributeListItems({ ir, mappings, facts, resolutions: resolved });
    const b = distributeListItems({ ir, mappings, facts, resolutions: reversed });
    const c = distributeListItems({ ir, mappings, facts, resolutions: inIrOrder });
    expect(b.map((r) => r.fieldId)).toEqual(reversed.map((r) => r.fieldId));
    expect(c.map((r) => r.fieldId)).toEqual(inIrOrder.map((r) => r.fieldId));
    for (const field of ir.fields) {
      expect(resolutionOf(b, field)).toEqual(resolutionOf(a, field));
      expect(resolutionOf(c, field)).toEqual(resolutionOf(a, field));
    }
    // non-vacuity: the pass did move something
    expect(canonicalSha256(a)).not.toBe(canonicalSha256(resolved));
  });

  it('two fills of the same input give the same manifest sha; no fact is minted', async () => {
    const { source, ir, mappings } = await pmhForm();
    const facts = pmhFacts('a2', ITEMS.slice(0, 2));
    const one = await prepare({ ir, source, mappings, facts });
    const two = await prepare({ ir, source, mappings, facts });
    expect(one.manifestSha256).toBe(two.manifestSha256);
    expect(one.factSetSha256).toBe(canonicalSha256(facts));
    expect(one.manifest.facts).toEqual(facts);
  });
});

// ============================================================================
// A3 · THE K MATRIX, THROUGH THE REAL VALIDATOR AND RENDERER.
// ============================================================================
describe('#313 A3 — K items into N = 3 bullets', () => {
  it.each([1, 2, 3, 4, 6])('K = %i', async (k) => {
    const { source, ir, mappings, members } = await pmhForm();
    const values = ITEMS.slice(0, k);
    const facts = pmhFacts(`k${k}`, values);
    const prepared = await prepare({ ir, source, mappings, facts });
    const res = members.map((m) => resolutionOf(prepared.manifest.fields, m));

    const cited = res.flatMap((r) => r.sourceFactIds);
    expect(new Set(cited).size, 'a fact is cited by two bullets').toBe(cited.length);
    expect(new Set(cited)).toEqual(new Set(listItemCandidates(mappings[0]!, facts).map((f) => f.factId)));
    expect(res.filter((r) => r.value !== null)).toHaveLength(Math.min(k, 3));
    if (k > 3) expect(res[2]!.value).toBe(values.slice(2).join('; '));
    else values.forEach((value, index) => expect(res[index]!.value).toBe(value));
    expect(blocking(prepared.manifest.validation.issues)).toEqual([]);
    expect(prepared.render).not.toBeNull();
    expect(prepared.render!.verification.verified).toBe(true);
    const texts = await controlTexts(prepared.render!.document);
    expect(texts).toEqual(res.map((r) => (r.value === null ? '' : String(r.value))));
    const counts = prepared.manifest.counts;
    if (k < 3) expect(counts.slotsUnused).toBe(3 - k);
    else expect('slotsUnused' in counts).toBe(false);
  });
});

// ============================================================================
// A4 · BYTE-IDENTITY.
// ============================================================================
describe('#313 A4 — values are the cited facts\' own, byte for byte', () => {
  async function distributed(values: string[]) {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts(values.join('|'), values);
    const out = distributeListItems({ ir, mappings, facts, resolutions: resolveAll(ir, mappings, facts) });
    const validation = validateAll(ir, mappings, facts, out);
    return { res: members.map((m) => resolutionOf(out, m)), validation, facts };
  }

  it('a lone "CVI " on its own bullet stays UNTRIMMED (the strict one-fact path)', async () => {
    const { res, validation } = await distributed(['CVI ', 'Hypertension']);
    expect(res[0]!.value).toBe('CVI ');
    expect(res[1]!.value).toBe('Hypertension');
    expect(validation.valid).toBe(true);
  });

  it('"HTN" and "HTN " are ONE item — one bullet citing both, valued "HTN"', async () => {
    const { res, validation, facts } = await distributed(['HTN', 'HTN ', 'Asthma']);
    expect(res[0]).toMatchObject({ value: 'HTN', reasonCode: 'list_valued_narrative_joined' });
    expect(res[0]!.sourceFactIds).toEqual([facts[0]!.factId, facts[1]!.factId]);
    expect(res[1]!.value).toBe('Asthma');
    expect(res[2]!.reasonCode).toBe(LIST_ITEM_SLOT_UNUSED_REASON);
    expect(validation.valid).toBe(true);
  });

  it('an item that itself contains "; " stays WHOLE on one bullet — never split', async () => {
    const { res, validation } = await distributed(['Hypertension; well controlled', 'Asthma']);
    expect(res[0]!.value).toBe('Hypertension; well controlled');
    expect(res[1]!.value).toBe('Asthma');
    expect(validation.valid).toBe(true);
  });
});

// ============================================================================
// A5 · ONE ITEM IN A LONGER GROUP — BULLET 1 BYTE-IDENTICAL TO TODAY.
// ============================================================================
describe('#313 A5 — Impression ×4 with one assessment', () => {
  it('bullet 1 is today\'s resolution exactly; three unused; counts move out of notMentioned', async () => {
    const { ir } = await compiledForm([heading('Impression'), ...bullets('Impression', 'impression', 4, 40)]);
    const mappings = mappingsFor(ir, { Impression: 'assessment' });
    const members = membersByAlias(ir, 'Impression');
    const facts = [fact('a5', 'assessment', 'Chronic venous insufficiency')];
    const today = resolveAll(ir, mappings, facts);
    const out = distributeListItems({ ir, mappings, facts, resolutions: today });
    expect(resolutionOf(out, members[0]!)).toEqual(resolutionOf(today, members[0]!));
    expect(members.slice(1).map((m) => resolutionOf(out, m).reasonCode)).toEqual([
      LIST_ITEM_SLOT_UNUSED_REASON,
      LIST_ITEM_SLOT_UNUSED_REASON,
      LIST_ITEM_SLOT_UNUSED_REASON,
    ]);
    const before = templateTwinCounts(today, ir.fields);
    const after = templateTwinCounts(out, ir.fields);
    expect(after.filled).toBe(1);
    expect(after.slotsUnused).toBe(3);
    expect(after.notMentioned).toBe(before.notMentioned); // the header control only
    expect(before.filled).toBe(4); // today: the one assessment printed four times
  });
});

// ============================================================================
// A6 · MIXED POLARITY — THE DENIAL RIDES ON BULLET 1, AND WARNS ONCE.
// ============================================================================
describe('#313 A6 — mixed polarity', () => {
  it('[HTN, denied DM, asthma] -> "HTN" (mixed) / "asthma" / unused, ONE warning on bullet 1', async () => {
    const { ir, mappings, members } = await pmhForm();
    const facts = [
      fact('a6-1', 'past_medical_history', 'HTN'),
      fact('a6-2', 'past_medical_history', 'DM', { polarity: 'denied' }),
      fact('a6-3', 'past_medical_history', 'asthma'),
    ];
    const today = resolveAll(ir, mappings, facts);
    expect(resolutionOf(today, members[0]!).reasonCode).toBe(MIXED_POLARITY_REASON);
    const out = distributeListItems({ ir, mappings, facts, resolutions: today });
    const [b1, b2, b3] = members.map((m) => resolutionOf(out, m));
    expect(b1).toMatchObject({ value: 'HTN', reasonCode: MIXED_POLARITY_REASON });
    expect(b1!.sourceFactIds).toEqual([facts[0]!.factId, facts[1]!.factId]);
    expect(b2).toMatchObject({ value: 'asthma', reasonCode: 'direct_evidence_supported' });
    expect(b3!.reasonCode).toBe(LIST_ITEM_SLOT_UNUSED_REASON);
    const warn = (resolutions: FieldResolution[]) =>
      validateAll(ir, mappings, facts, resolutions).issues.filter(
        (issue) => issue.code === 'FIELD_MIXED_POLARITY_DENIAL_WITHHELD',
      );
    expect(warn(out).map((issue) => issue.fieldId)).toEqual([members[0]!.fieldId]);
    // twin: today the same denial is reported once PER BULLET
    expect(warn(today)).toHaveLength(3);
    expect(validateAll(ir, mappings, facts, out).valid).toBe(true);
  });
});

// ============================================================================
// A8 · LATERALITY — A CONFLICT IS NEVER SPLIT INTO SINGLE-FACT BULLETS.
// ============================================================================
describe('#313 A8 — a left + right mix stays a conflict, untouched', () => {
  it('conflict in, conflict out, byte-identical', async () => {
    const { ir, mappings } = await pmhForm();
    const facts = [
      fact('a8-l', 'past_medical_history', 'Varicose veins', { laterality: 'left' }),
      fact('a8-r', 'past_medical_history', 'Venous ulcer', { laterality: 'right' }),
    ];
    const today = resolveAll(ir, mappings, facts);
    const plan = planListDistribution({ ir, mappings, facts, resolutions: today });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'untouched', reason: 'member_not_distributable' }]);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(today));
    // twin: one side only distributes
    const oneSide = facts.map((f) => ({ ...f, laterality: 'left' as const }));
    const twin = planListDistribution({ ir, mappings, facts: oneSide, resolutions: resolveAll(ir, mappings, oneSide) });
    expect(twin.outcomes[0]!.outcome.kind).toBe('distributed');
  });
});

// ============================================================================
// A9 · THE SECOND READER — hand-built manifests, no distributor involved.
// ============================================================================
describe('#313 A9 — the validator\'s group checks', () => {
  async function setup(required = false, extraFacts: EncounterFact[] = []) {
    const { ir, members } = await pmhForm();
    const mappings = mappingsFor(ir, PMH_CONCEPTS, () => (required ? { required: true } : {}));
    const dictated = pmhFacts('a9', ['Hypertension', 'Asthma']);
    const facts = [...dictated, ...extraFacts];
    const base = resolveAll(ir, mappings, dictated);
    const one = (fieldId: string, f: EncounterFact): FieldResolution => ({
      fieldId,
      status: 'supported',
      value: String(f.value),
      sourceFactIds: [f.factId],
      evidenceAnchorIds: [...f.evidenceAnchorIds],
      selectedOptionOrdinal: null,
      reasonCode: 'direct_evidence_supported',
      clinicianReviewed: false,
    });
    const slot = (fieldId: string, patch: Partial<FieldResolution> = {}): FieldResolution => ({
      fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: LIST_ITEM_SLOT_UNUSED_REASON,
      clinicianReviewed: false,
      ...patch,
    });
    const withGroup = (group: FieldResolution[]) =>
      base.map((r) => group.find((g) => g.fieldId === r.fieldId) ?? r);
    const ids = members.map((m) => m.fieldId) as [string, string, string];
    const run = (group: FieldResolution[]) => validateAll(ir, mappings, facts, withGroup(group));
    return { ir, facts: dictated, one, slot, ids, run, base, mappings };
  }
  const codes = (v: { issues: ReadonlyArray<{ code: string; severity: string }> }) =>
    v.issues.map((i) => `${i.code}:${i.severity}`);

  it('POSITIVE: one item per bullet plus a trailing unused bullet raises nothing', async () => {
    const { one, slot, ids, run, facts } = await setup();
    const v = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2])]);
    expect(v.valid).toBe(true);
    expect(codes(v).filter((c) => c.startsWith('LIST_'))).toEqual([]);
  });

  it('an item that reached no bullet -> LIST_ITEM_DROPPED, blocking', async () => {
    const { one, slot, ids, run, facts } = await setup();
    const v = run([one(ids[0], facts[0]!), slot(ids[1]), slot(ids[2])]);
    expect(codes(v)).toContain(`${LIST_ITEM_DROPPED}:blocking`);
    expect(v.valid).toBe(false);
  });

  it('an item on two bullets -> LIST_ITEM_REPEATED, a WARNING (never withholds)', async () => {
    const { one, ids, run, facts } = await setup();
    const v = run([one(ids[0], facts[0]!), one(ids[1], facts[0]!), one(ids[2], facts[1]!)]);
    expect(codes(v)).toContain(`${LIST_ITEM_REPEATED}:warning`);
    expect(v.valid).toBe(true);
  });

  it('TODAY\'S SHAPE (every bullet the whole list) is a REPEATED warning, not a withheld document', async () => {
    const { run, base, ids } = await setup();
    const v = run(ids.map((id) => resolutionOf(base, { fieldId: id })));
    expect(codes(v)).toContain(`${LIST_ITEM_REPEATED}:warning`);
    expect(v.valid).toBe(true);
  });

  it('the unused-bullet token on a control outside any group -> ILLEGITIMATE', async () => {
    const { ir, one, slot, ids, run, facts } = await setup();
    const header = ir.fields.find((f) => f.rendererBinding.partName !== 'word/document.xml')!;
    const v = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2]), slot(header.fieldId)]);
    expect(v.issues.filter((i) => i.code === LIST_SLOT_UNUSED_ILLEGITIMATE).map((i) => i.fieldId)).toEqual([header.fieldId]);
    expect(v.valid).toBe(false);
  });

  it('an unused bullet BEFORE an item -> ILLEGITIMATE', async () => {
    const { one, slot, ids, run, facts } = await setup();
    const v = run([slot(ids[0]), one(ids[1], facts[0]!), one(ids[2], facts[1]!)]);
    expect(v.issues.filter((i) => i.code === LIST_SLOT_UNUSED_ILLEGITIMATE).map((i) => i.fieldId)).toEqual([ids[0]]);
  });

  it('a group of ONLY unused bullets -> ILLEGITIMATE, and the document is REFUSED', async () => {
    const { slot, ids, run } = await setup();
    const v = run([slot(ids[0]), slot(ids[1]), slot(ids[2])]);
    expect(v.issues.filter((i) => i.code === LIST_SLOT_UNUSED_ILLEGITIMATE)).toHaveLength(3);
    // ⚠️ #313 ROUND ONE: DROPPED is no longer CO-reported here. A group in which
    // no bullet carries a dictated item is skipped by DROPPED/REPEATED (the doctor's
    // default on every bullet over an uncertain fact was being withheld by it). This
    // shape is still refused, by ILLEGITIMATE alone, and that is the assertion.
    expect(codes(v)).toContain(`${LIST_SLOT_UNUSED_ILLEGITIMATE}:blocking`);
    expect(codes(v)).not.toContain(`${LIST_ITEM_DROPPED}:blocking`);
    expect(v.valid).toBe(false);
  });

  it('the token on a non-blank status -> ILLEGITIMATE', async () => {
    const { one, slot, ids, run, facts } = await setup();
    const v = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2], { status: 'needs_clinician_input' })]);
    expect(v.issues.filter((i) => i.code === LIST_SLOT_UNUSED_ILLEGITIMATE).map((i) => i.fieldId)).toEqual([ids[2]]);
  });

  it('REQUIRED: a legitimate unused bullet is exempt; the SAME blank as fact_not_mentioned still blocks', async () => {
    const { one, slot, ids, run, facts } = await setup(true);
    const legit = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2])]);
    expect(codes(legit)).not.toContain('REQUIRED_FIELD_NOT_MENTIONED:blocking');
    expect(legit.valid).toBe(true);
    const plain = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2], { reasonCode: 'fact_not_mentioned' })]);
    expect(codes(plain)).toContain('REQUIRED_FIELD_NOT_MENTIONED:blocking');
  });

  it('REQUIRED: an ILLEGITIMATE unused bullet (before an item) is NOT exempt', async () => {
    // ⚠️ The exemption is keyed on LEGITIMACY, never on the token alone —
    // otherwise the token would be a way to blank any required field.
    const { one, slot, ids, run, facts } = await setup(true);
    const v = run([slot(ids[0]), one(ids[1], facts[0]!), one(ids[2], facts[1]!)]);
    expect(codes(v)).toContain('REQUIRED_FIELD_NOT_MENTIONED:blocking');
    expect(codes(v)).toContain(`${LIST_SLOT_UNUSED_ILLEGITIMATE}:blocking`);
  });

  it('an all-DENIED group (every bullet withheld, one denied fact) raises NO list issue', async () => {
    // ⚠️ A FALSE REJECTION THIS ARM EXISTS TO PREVENT: FH ×3 dictated as "no
    // family history of colon cancer" is `denial_withheld` on every bullet,
    // each citing the same denied fact. Counting that as "printed twice" would
    // cost the form its certificate for a blank nobody printed.
    const { ir, members } = await pmhForm();
    const mappings = mappingsFor(ir, PMH_CONCEPTS);
    const facts = [fact('a9-den', 'past_medical_history', 'Colon cancer', { polarity: 'denied' })];
    const resolved = resolveAll(ir, mappings, facts);
    expect(resolutionOf(resolved, members[0]!).status).toBe('denial_withheld');
    expect(resolutionOf(resolved, members[1]!).sourceFactIds).toEqual([facts[0]!.factId]);
    const v = validateAll(ir, mappings, facts, resolved);
    expect(v.issues.filter((issue) => issue.code.startsWith('LIST_'))).toEqual([]);
    expect(canonicalSha256(distributeListItems({ ir, mappings, facts, resolutions: resolved }))).toBe(
      canonicalSha256(resolved),
    );
  });

  it('a NON-dictated fact carrying the list concept (a pick) is not a droppable item', async () => {
    const pick = fact('a9-pick', 'past_medical_history', 'Hypertension', { sourceType: 'verified_note_selection' });
    const { one, slot, ids, run, facts } = await setup(false, [pick]);
    const v = run([one(ids[0], facts[0]!), one(ids[1], facts[1]!), slot(ids[2])]);
    expect(codes(v).filter((c) => c.startsWith('LIST_'))).toEqual([]);
    expect(v.valid).toBe(true);
  });

  it('REQUIRED, through the fill: a one-item list on required bullets still renders', async () => {
    const { source, ir, members } = await pmhForm();
    const mappings = mappingsFor(ir, PMH_CONCEPTS, () => ({ required: true }));
    const prepared = await prepare({ ir, source, mappings, facts: pmhFacts('req', ['Hypertension']) });
    expect(members.slice(1).map((m) => resolutionOf(prepared.manifest.fields, m).reasonCode)).toEqual([
      LIST_ITEM_SLOT_UNUSED_REASON,
      LIST_ITEM_SLOT_UNUSED_REASON,
    ]);
    expect(prepared.manifest.validation.valid).toBe(true);
    expect(prepared.render).not.toBeNull();
  });
});

// ============================================================================
// A10 · CANDIDATE DRIFT — THE RESOLVER CITES EXACTLY `listItemCandidates`.
// ============================================================================
describe('#313 A10 — R cites exactly the candidate set, for every eligible reason', () => {
  const distractors = (mapping: SemanticMapping, field: { fieldId: string }): EncounterFact[] => {
    const defaultId = approvedPracticeDefaultFactId(field as never, mapping);
    return [
      fact('d-plan', 'plan', 'Follow up in three months'),
      fact('d-tense', 'past_medical_history', 'Old fracture', { temporality: 'planned' }),
      fact('d-default', 'past_medical_history', 'Default text', {
        factId: defaultId,
        sourceType: 'approved_practice_default',
        evidenceAnchorIds: [approvedPracticeDefaultAnchorId(field as never, defaultId)],
      }),
    ];
  };
  it.each([
    ['direct_evidence_supported', [['Hypertension', 'affirmed']]],
    ['list_valued_narrative_joined', [['Hypertension', 'affirmed'], ['Asthma', 'affirmed']]],
    [MIXED_POLARITY_REASON, [['Hypertension', 'affirmed'], ['Asthma', 'denied']]],
  ] as const)('%s', async (reason, spec) => {
    const { ir, members } = await pmhForm();
    const mappings = mappingsFor(ir, PMH_CONCEPTS, () => ({ temporality: 'current' }));
    const mapping = mappings.find((m) => m.fieldId === members[0]!.fieldId)!;
    const facts = [
      ...spec.map(([value, polarity], index) =>
        fact(`a10-${reason}-${index}`, 'past_medical_history', value, { polarity }),
      ),
      ...distractors(mapping, members[0]!),
    ];
    const r = resolutionOf(resolveAll(ir, mappings, facts), members[0]!);
    expect(r.reasonCode).toBe(reason);
    expect(new Set(r.sourceFactIds)).toEqual(new Set(listItemCandidates(mapping, facts).map((f) => f.factId)));
    expect(r.sourceFactIds).toHaveLength(spec.length);
  });
});

// ============================================================================
// A11 · THE FALLBACK — a failing self-check COLLAPSES, and the collapse validates.
// ============================================================================
describe('#313 A11 — collapse rather than withhold', () => {
  it('an injected failing check yields "bullet 1 = today, the rest unused", valid', async () => {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a11', ITEMS.slice(0, 3));
    const today = resolveAll(ir, mappings, facts);
    const plan = planListDistribution({ ir, mappings, facts, resolutions: today, acceptDistribution: () => false });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'collapsed', reason: 'self_check_failed' }]);
    expect(resolutionOf(plan.resolutions, members[0]!)).toEqual(resolutionOf(today, members[0]!));
    expect(members.slice(1).map((m) => resolutionOf(plan.resolutions, m).reasonCode)).toEqual([
      LIST_ITEM_SLOT_UNUSED_REASON,
      LIST_ITEM_SLOT_UNUSED_REASON,
    ]);
    expect(blocking(validateAll(ir, mappings, facts, plan.resolutions).issues)).toEqual([]);
    // twin: without the injection it DISTRIBUTES
    const real = planListDistribution({ ir, mappings, facts, resolutions: today });
    expect(real.outcomes[0]!.outcome).toEqual({ kind: 'distributed', items: 3, bullets: 3 });
  });
});

describe('#313 A11b — a group citing anything but dictation is left exactly as it is', () => {
  it('bullets that all cite one clinician-correction fact are untouched', async () => {
    const { ir, mappings, members } = await pmhForm();
    const correction = fact('a11b', 'past_medical_history', 'Hypertension', { sourceType: 'clinician_correction' });
    const dictated = pmhFacts('a11b', ['Asthma']);
    const facts = [correction, ...dictated];
    const base = resolveAll(ir, mappings, dictated);
    const shared: FieldResolution = {
      fieldId: '',
      status: 'supported',
      value: 'Hypertension',
      sourceFactIds: [correction.factId],
      evidenceAnchorIds: [...correction.evidenceAnchorIds],
      selectedOptionOrdinal: null,
      reasonCode: 'direct_evidence_supported',
      clinicianReviewed: false,
    };
    const input = base.map((r) =>
      members.some((m) => m.fieldId === r.fieldId) ? { ...shared, fieldId: r.fieldId } : r,
    );
    const plan = planListDistribution({ ir, mappings, facts, resolutions: input });
    expect(plan.outcomes.map((o) => o.outcome.kind)).toEqual(['untouched']);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(input));
  });

  // ⚠️ A GROUP THAT IS NOT `supported` IS NEVER REWRITTEN — every rewritten
  // bullet is minted `supported`, so redistributing a `record_derived` group
  // would silently relabel record values as DICTATED (#247), and the self-check
  // would not notice (it only compares blocking issues).
  it.each([
    ['record_derived', { status: 'record_derived' as const }],
    ['clinician-reviewed', { clinicianReviewed: true }],
  ])('a %s group is left exactly as it is', async (_name, patch) => {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a11d', ITEMS.slice(0, 2));
    const today = resolveAll(ir, mappings, facts);
    const input = today.map((r) => (members.some((m) => m.fieldId === r.fieldId) ? { ...r, ...patch } : r));
    const plan = planListDistribution({ ir, mappings, facts, resolutions: input });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'untouched', reason: 'member_not_distributable' }]);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(input));
  });

  // ⚠️ THE BUILT-IN SELF-CHECK, WIRED BY DEFAULT — no injection. The battery
  // found it (and the collapse re-check) masked by the dictated-only test for
  // every other input. Here the cited fact IS dictated but belongs to another
  // concept: K = 1, so the proposal IS the collapse, and its unused bullets
  // are illegitimate (the list has no item of its own). Only the validator
  // comparison can see that, and it must leave the group exactly as it came.
  it('a group citing a dictated fact OUTSIDE its own mapping is left untouched — the self-check', async () => {
    const { ir, mappings, members } = await pmhForm();
    const stray = fact('a11e', 'plan', 'Follow up in three months');
    const base = resolveAll(ir, mappings, []);
    const input = base.map((r) =>
      members.some((m) => m.fieldId === r.fieldId)
        ? {
            ...r,
            status: 'supported' as const,
            value: 'Follow up in three months',
            sourceFactIds: [stray.factId],
            evidenceAnchorIds: [...stray.evidenceAnchorIds],
            selectedOptionOrdinal: null,
            reasonCode: 'direct_evidence_supported',
            clinicianReviewed: false,
          }
        : r,
    );
    const plan = planListDistribution({ ir, mappings, facts: [stray], resolutions: input });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'untouched', reason: 'collapse_failed_self_check' }]);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(input));
  });

  // ⚠️ K = N WITH NON-DICTATED ITEMS — no unused bullet, so the self-check has
  // nothing to object to and only the dictated-only test refuses. Correction
  // facts belong to the bullet a doctor minted them for; they are never items.
  it('three non-dictated items on three bullets are STILL left untouched', async () => {
    const { ir, mappings, members } = await pmhForm();
    const corrections = ['Hypertension', 'Asthma', 'Gout'].map((value, index) =>
      fact(`a11f-${index}`, 'past_medical_history', value, { sourceType: 'clinician_correction' }),
    );
    const base = resolveAll(ir, mappings, []);
    const input = base.map((r) =>
      members.some((m) => m.fieldId === r.fieldId)
        ? {
            ...r,
            status: 'supported' as const,
            value: 'Hypertension; Asthma; Gout',
            sourceFactIds: corrections.map((f) => f.factId),
            evidenceAnchorIds: corrections.flatMap((f) => f.evidenceAnchorIds),
            selectedOptionOrdinal: null,
            reasonCode: 'list_valued_narrative_joined',
            clinicianReviewed: false,
          }
        : r,
    );
    const plan = planListDistribution({ ir, mappings, facts: corrections, resolutions: input });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'untouched', reason: 'cited_fact_not_dictated' }]);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(input));
  });

  it('members that did NOT come out of the resolver identical are untouched', async () => {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a11c', ITEMS.slice(0, 2));
    const today = resolveAll(ir, mappings, facts);
    // bullet 2 cites only the first item — a shape no single mapping produces,
    // and exactly the doubt the eligibility rule exists to refuse.
    const first = facts[0]!;
    const input = today.map((r) =>
      r.fieldId === members[1]!.fieldId
        ? { ...r, value: String(first.value), sourceFactIds: [first.factId], evidenceAnchorIds: [...first.evidenceAnchorIds], reasonCode: 'direct_evidence_supported' }
        : r,
    );
    const plan = planListDistribution({ ir, mappings, facts, resolutions: input });
    expect(plan.outcomes.map((o) => o.outcome)).toEqual([{ kind: 'untouched', reason: 'members_differ' }]);
    expect(canonicalSha256(plan.resolutions)).toBe(canonicalSha256(input));
  });
});

// ============================================================================
// A12 · COUNTS — a zero-group manifest recomputes byte-identically.
// ============================================================================
describe('#313 A12 — counts', () => {
  it('no group: no `slotsUnused` key, the pre-#313 shape exactly', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const stored = withoutSoleParagraphControl(ir);
    const mappings = mappingsFor(stored, PMH_CONCEPTS);
    const facts = pmhFacts('a12', ITEMS.slice(0, 2));
    const out = distributeListItems({ ir: stored, mappings, facts, resolutions: resolveAll(stored, mappings, facts) });
    const counts = templateTwinCounts(out, stored.fields);
    expect('slotsUnused' in counts).toBe(false);
    expect(canonicalSha256(counts)).toBe(
      canonicalSha256({ filled: 3, needsReview: 0, notMentioned: 1, omitted: 0, conflicts: 0, criticalUnresolved: 0 }),
    );
  });

  it('with a group: every field in exactly one bucket', async () => {
    const { ir, mappings } = await pmhForm();
    const facts = pmhFacts('a12b', ITEMS.slice(0, 1));
    const out = distributeListItems({ ir, mappings, facts, resolutions: resolveAll(ir, mappings, facts) });
    const c = templateTwinCounts(out, ir.fields);
    expect(c.filled + c.notMentioned + (c.omitted ?? 0) + (c.slotsUnused ?? 0) + c.needsReview).toBe(ir.fields.length);
    expect(c).toMatchObject({ filled: 1, notMentioned: 1, slotsUnused: 2 });
  });
});

// ============================================================================
// A14 · THE OFFER — withdrawn on an unused bullet; a stored default still applies.
// ============================================================================
describe('#313 A14 — "insert your default" on an unused bullet (O3)', () => {
  it('not offered on an unused bullet; offered on the same field when it is a plain blank', async () => {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a14', ITEMS.slice(0, 1));
    const out = distributeListItems({ ir, mappings, facts, resolutions: resolveAll(ir, mappings, facts) });
    const bullet3 = members[2]!;
    expect(bullet3.scaffolded).toBe(true);
    const current = resolutionOf(out, bullet3);
    expect(current.reasonCode).toBe(LIST_ITEM_SLOT_UNUSED_REASON);
    const offer = (c: FieldResolution) =>
      scaffoldDefaultOfferable({ field: bullet3, mapping: { clinicalConcept: 'past_medical_history' }, current: c });
    expect(offer(current)).toBe(false);
    expect(offer({ ...current, reasonCode: 'fact_not_mentioned' })).toBe(true);
  });

  it('a default the doctor ALREADY inserted on that bullet still applies', async () => {
    const { ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a14b', ITEMS.slice(0, 1));
    const out = distributeListItems({ ir, mappings, facts, resolutions: resolveAll(ir, mappings, facts) });
    const applied = applyClinicianOverrides({
      ir,
      resolutions: out,
      overrides: [{ kind: 'scaffold_default', fieldId: members[2]!.fieldId, insertedText: '- ____' }],
      mappings,
      noteSha256: '',
    });
    expect(applied.declined).toEqual([]);
    expect(resolutionOf(applied.resolutions, members[2]!).reasonCode).toBe('clinician_scaffold_default');
  });
});

// ============================================================================
// A15 · THE BRIDGES NEVER REACH A NARRATIVE BULLET.
// ============================================================================
describe('#313 A15 — a note listing PMH items leaves the unused bullets unused', () => {
  it('with and without a generated note, the group is identical', async () => {
    const { source, ir, mappings, members } = await pmhForm();
    const facts = pmhFacts('a15', ['Hypertension']);
    const note =
      '## Past Medical History\n- Hypertension\n- Type 2 diabetes mellitus\n- Asthma\n\n' +
      '| Past Medical History | Value |\n|---|---|\n| Hypertension | yes |\n';
    const bridged = await prepare({ ir, source, mappings, facts, markerText: 'Past Medical History {{one of: yes|no}}', generatedNote: note });
    const plain = await prepare({ ir, source, mappings, facts });
    for (const member of members) {
      expect(resolutionOf(bridged.manifest.fields, member)).toEqual(resolutionOf(plain.manifest.fields, member));
    }
    expect(resolutionOf(bridged.manifest.fields, members[2]!).reasonCode).toBe(LIST_ITEM_SLOT_UNUSED_REASON);
  });
});

// ============================================================================
// ROUND ONE — THE DOCTOR'S DEFAULT ON EVERY BULLET NEVER WITHHOLDS THE DOCUMENT.
// ----------------------------------------------------------------------------
// The refutation pass drove this through the real prepareTemplateTwinFill: with
// the doctor's scaffold default inserted on EVERY bullet over an uncertain,
// unclear or other-experiencer fact, the pass left the group untouched — and the
// new LIST_ITEM_DROPPED check counted that fact as a dropped item and withheld a
// document that rendered before #313. The group checks now skip a group in which
// no bullet carries a dictated item. Each case runs twice: with the property
// (post-#313) and without it (pre-#313 parity), and the two must agree.
// ============================================================================
describe('#313 round one — defaults on every bullet over an undistributable fact', () => {
  const cases: Array<[string, EncounterFact[]]> = [
    ['an uncertain second item', [
      fact('r1-a', 'past_medical_history', 'Hypertension'),
      fact('r1-b', 'past_medical_history', 'Diabetes', { polarity: 'uncertain' }),
    ]],
    ['an unclear-evidence item', [
      fact('r1-c', 'past_medical_history', 'Hypertension', { quality: { asr: 'high', evidence: 'unclear' } }),
    ]],
    ['another experiencer\'s item', [
      fact('r1-d', 'past_medical_history', 'Diabetes', { experiencer: 'other' }),
    ]],
  ];

  it.each(cases)('%s — the document renders, and the defaults stand', async (_what, facts) => {
    const { source, ir, mappings, members } = await pmhForm();
    const clinicianOverrides = members.map((m) => ({ kind: 'scaffold_default' as const, fieldId: m.fieldId, insertedText: 'None' }));
    const post = await prepare({ ir, source, mappings, facts, clinicianOverrides });
    const pre = await prepare({ ir: withoutSoleParagraphControl(ir), source, mappings, facts, clinicianOverrides });

    expect(blocking(post.manifest.validation.issues)).not.toContain('LIST_ITEM_DROPPED');
    expect(post.manifest.validation.valid, 'post-#313 withheld a document').toBe(true);
    // PARITY, not merely validity: #313 changes nothing about this document.
    expect(post.manifest.validation.valid).toBe(pre.manifest.validation.valid);
    expect(members.map((m) => resolutionOf(post.manifest.fields, m)!.value)).toEqual(
      members.map((m) => resolutionOf(pre.manifest.fields, m)!.value),
    );
    for (const m of members) expect(resolutionOf(post.manifest.fields, m)!.value).toBe('None');
  });
});
